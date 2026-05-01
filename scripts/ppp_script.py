if __name__ == "__main__":
    raise SystemExit("This script must be run from a Stable Diffusion WebUI")

import logging
import sys
import os
import time
from pathlib import Path
import numpy as np

sys.path.append(str(Path(__file__).parent))  # base path for the extension

from modules import scripts, shared, script_callbacks  # type: ignore
from modules.processing import StableDiffusionProcessing  # type: ignore
from modules.shared import opts  # type: ignore
from modules.paths import models_path  # type: ignore
import gradio as gr  # type: ignore
from ppp import PromptPostProcessor
from ppp_classes import IFWILDCARDS_CHOICES, ONWARNING_CHOICES, SUPPORTED_APPS, SUPPORTED_APPS_NAMES, PPPStateOptions
from ppp_logging import DEBUG_LEVEL, PromptPostProcessorLogFactory, log
from ppp_cache import PPPLRUCache
from ppp_wildcards import PPPWildcards
from ppp_enmappings import PPPExtraNetworkMappings


class PromptPostProcessorA1111Script(scripts.Script):
    """
    This class represents a script for prompt post-processing.
    It is responsible for processing prompts and applying various settings and cleanup operations.

    Attributes:
        callbacks_added (bool): Flag indicating whether the script callbacks have been added.

    Methods:
        __init__(): Initializes the PromptPostProcessorScript object.
        title(): Returns the title of the script.
        show(is_img2img): Determines whether the script should be shown based on the input type.
        process(p, *args, **kwargs): Processes the prompts and applies post-processing operations.
        ppp_interrupt(): Interrupts the generation.
        __on_ui_settings(): Callback function for UI settings.
    """

    instance_count = 0

    @classmethod
    def increment_instance_count(cls):
        cls.instance_count += 1
        return cls.instance_count

    @classmethod
    def get_instance_count(cls):
        return cls.instance_count

    def __init__(self):
        """
        Initializes the PromptPostProcessor object.

        Parameters:
            None

        Returns:
            None
        """
        self.instance_index = self.increment_instance_count()
        self.name = PromptPostProcessor.NAME
        grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../grammar.lark")
        with open(grammar_filename, "r", encoding="utf-8") as file:
            self.grammar_content = file.read()
        self.ppp_logger = None
        self.ppp_debug_level = DEBUG_LEVEL.none.value
        self.lru_cache = None
        self.wildcards_obj = None
        self.extranetwork_mappings_obj = None

    def title(self):
        """
        Returns the title of the script.

        Returns:
            str: The title of the script.
        """
        return PromptPostProcessor.NAME

    def show(self, is_img2img):  # pylint: disable=unused-argument
        """
        Determines whether the script should be shown based on the kind of processing.

        Args:
            is_img2img (bool): Flag indicating whether the processing is image-to-image.

        Returns:
            scripts.Visibility: The visibility setting for the script.
        """
        return scripts.AlwaysVisible

    def ui(self, is_img2img):  # pylint: disable=unused-argument
        with gr.Accordion(PromptPostProcessor.NAME, open=False):
            force_equal_seeds = gr.Checkbox(
                label="Force equal seeds",
                info="Force all image seeds and variation seeds to be equal to the first one, disabling the default autoincrease.",
                value=False,
                # show_label=True,
                elem_id="ppp_force_equal_seeds",
            )
            gr.HTML("<br>")
            gr.Markdown(
                """
                Unlink the seed to use the specified one for the prompts instead of the image seed.

                * A seed of -1 and "Incremental seed" checked will use a random seed for the first prompt and consecutive values for the rest. This is the same as when you use -1 for the image seed.
                * A seed of -1 and "Incremental seed" unchecked will use a random seed for each prompt.
                * Any other seed value and "Incremental seed" checked will use the specified seed for the first prompt and consecutive values for the rest.
                * Any other seed value and "Incremental seed" unchecked will use the specified seed for all the prompts.

                Seeds are only used for the wildcards and choice constructs.
            """
            )
            gr.HTML("<br>")
            with gr.Row(equal_height=True):
                unlink_seed = gr.Checkbox(
                    label="Unlink seed",
                    value=False,
                    # show_label=True,
                    elem_id="ppp_unlink_seed",
                )
                seed = gr.Number(
                    label="Prompt seed",
                    value=-1,
                    precision=0,
                    # minimum=-1,
                    # maximum=2**32 - 1,
                    # step=1,
                    # show_label=True,
                    min_width=100,
                    elem_id="ppp_seed",
                )
                incremental_seed = gr.Checkbox(
                    label="Incremental seed (only applies to batches)",
                    value=False,
                    # show_label=True,
                    elem_id="ppp_incremental_seed",
                )
            gr.HTML("<br>")
            with gr.Row(equal_height=True):
                combinatorial = gr.Checkbox(
                    label="Combinatorial mode",
                    info="Generate all prompt combinations and cycle through them to fill the batch.",
                    value=PromptPostProcessor.DEFAULT_DO_COMBINATORIAL,
                    elem_id="ppp_combinatorial",
                )
                combinatorial_limit = gr.Number(
                    label="Combinations limit (0 = no limit)",
                    value=PromptPostProcessor.DEFAULT_COMBINATORIAL_LIMIT,
                    precision=0,
                    min_width=120,
                    elem_id="ppp_combinatorial_limit",
                )
        return [force_equal_seeds, unlink_seed, seed, incremental_seed, combinatorial, combinatorial_limit]

    def process(
        self,
        p: StableDiffusionProcessing,
        input_force_equal_seeds,
        input_unlink_seed,
        input_seed,
        input_incremental_seed,
        input_combinatorial,
        input_combinatorial_limit,
    ):  # pylint: disable=arguments-differ
        """
        Processes the prompts and applies post-processing operations.

        Args:
            p (StableDiffusionProcessing): The StableDiffusionProcessing object containing the prompts.
            input_force_equal_seeds (bool): Flag indicating whether to force equal seeds.
            input_unlink_seed (bool): Flag indicating whether to unlink the seed.
            input_seed (int): The seed value.
            input_incremental_seed (bool): Flag indicating whether to use incremental seed.
            input_combinatorial (bool): Flag indicating whether to use combinatorial mode.
            input_combinatorial_limit (int): Maximum number of combinations (0 = no limit).

        Returns:
            None
        """
        app = (
            SUPPORTED_APPS.forge
            if hasattr(p.sd_model, "model_config")
            else (
                SUPPORTED_APPS.reforge
                if hasattr(p.sd_model, "forge_objects")
                else (
                    SUPPORTED_APPS.sdnext
                    if hasattr(p.sd_model, "is_sdxl") and not hasattr(p.sd_model, "is_ssd")
                    else SUPPORTED_APPS.a1111
                )
            )
        )
        num_seeds = len(getattr(p, "all_seeds", []))
        options = PPPStateOptions(
            debug_level=DEBUG_LEVEL(getattr(opts, "ppp_gen_debug_level", PromptPostProcessor.DEFAULT_DEBUG_LEVEL)),
            on_warning=ONWARNING_CHOICES(getattr(opts, "ppp_gen_onwarning", PromptPostProcessor.DEFAULT_ON_WARNING)),
            strict_operators=getattr(opts, "ppp_gen_strict_operators", PromptPostProcessor.DEFAULT_STRICT_OPERATORS),
            process_wildcards=getattr(opts, "ppp_wil_processwildcards", PromptPostProcessor.DEFAULT_PROCESS_WILDCARDS),
            if_wildcards=IFWILDCARDS_CHOICES(
                getattr(opts, "ppp_wil_ifwildcards", PromptPostProcessor.DEFAULT_IF_WILDCARDS)
            ),
            choice_separator=getattr(opts, "ppp_wil_choice_separator", PromptPostProcessor.DEFAULT_CHOICE_SEPARATOR),
            keep_choices_order=getattr(
                opts, "ppp_wil_keep_choices_order", PromptPostProcessor.DEFAULT_KEEP_CHOICES_ORDER
            ),
            stn_separator=getattr(opts, "ppp_stn_separator", PromptPostProcessor.DEFAULT_STN_SEPARATOR),
            stn_ignore_repeats=getattr(opts, "ppp_stn_ignorerepeats", PromptPostProcessor.DEFAULT_STN_IGNORE_REPEATS),
            cup_do_cleanup=True,
            cup_cleanup_variables=True,
            cup_extra_spaces=getattr(opts, "ppp_cup_extraspaces", PromptPostProcessor.DEFAULT_CUP_EXTRA_SPACES),
            cup_empty_constructs=getattr(
                opts, "ppp_cup_emptyconstructs", PromptPostProcessor.DEFAULT_CUP_EMPTY_CONSTRUCTS
            ),
            cup_extra_separators=getattr(
                opts, "ppp_cup_extraseparators", PromptPostProcessor.DEFAULT_CUP_EXTRA_SEPARATORS
            ),
            cup_extra_separators2=getattr(
                opts, "ppp_cup_extraseparators2", PromptPostProcessor.DEFAULT_CUP_EXTRA_SEPARATORS2
            ),
            cup_extra_separators_include_eol=getattr(
                opts,
                "ppp_cup_extraseparators_include_eol",
                PromptPostProcessor.DEFAULT_CUP_EXTRA_SEPARATORS_INCLUDE_EOL,
            ),
            cup_breaks=getattr(opts, "ppp_cup_breaks", PromptPostProcessor.DEFAULT_CUP_BREAKS),
            cup_breaks_eol=getattr(opts, "ppp_cup_breaks_eol", PromptPostProcessor.DEFAULT_CUP_BREAKS_EOL),
            cup_ands=getattr(opts, "ppp_cup_ands", PromptPostProcessor.DEFAULT_CUP_ANDS),
            cup_ands_eol=getattr(opts, "ppp_cup_ands_eol", PromptPostProcessor.DEFAULT_CUP_ANDS_EOL),
            cup_extranetwork_tags=getattr(
                opts, "ppp_cup_extranetworktags", PromptPostProcessor.DEFAULT_CUP_EXTRANETWORK_TAGS
            ),
            cup_merge_attention=getattr(
                opts, "ppp_cup_mergeattention", PromptPostProcessor.DEFAULT_CUP_MERGE_ATTENTION
            ),
            cup_remove_extranetwork_tags=getattr(
                opts, "ppp_rem_removeextranetworktags", PromptPostProcessor.DEFAULT_CUP_REMOVE_EXTRANETWORK_TAGS
            ),
            do_combinatorial=input_combinatorial,
            combinatorial_limit=max(num_seeds, int(input_combinatorial_limit)) if input_combinatorial else 0,
        )
        if self.ppp_logger is None:
            lf = PromptPostProcessorLogFactory()
            self.ppp_logger = lf.log
            self.ppp_debug_level = options.debug_level
            self.lru_cache = PPPLRUCache(1000, logger=self.ppp_logger, debug_level=self.ppp_debug_level)
            self.wildcards_obj = PPPWildcards(self.ppp_logger)
            self.extranetwork_mappings_obj = PPPExtraNetworkMappings(self.ppp_logger)
            log(
                self.ppp_logger,
                DEBUG_LEVEL.minimal,
                logging.INFO,
                f"{PromptPostProcessor.NAME} {PromptPostProcessor.VERSION} initialized, running on {SUPPORTED_APPS_NAMES[app]}",
            )
        t1 = time.monotonic_ns()
        if getattr(opts, "prompt_attention", "") == "Compel parser":
            log(self.ppp_logger, self.ppp_debug_level, logging.WARNING, "Compel parser is not supported!")
        init_images = getattr(p, "init_images", [None]) or [None]
        is_i2i = bool(init_images[0])
        do_i2i = getattr(opts, "ppp_gen_doi2i", False)
        add_prompts = getattr(opts, "ppp_gen_addpromptstometadata", True)
        if is_i2i and not do_i2i:
            log(self.ppp_logger, self.ppp_debug_level, logging.INFO, "Not processing the prompt for i2i")
            return

        p.extra_generation_params.update(
            {
                "PPP force equal seeds": input_force_equal_seeds,
                "PPP unlink seed": input_unlink_seed,
                "PPP prompt seed": input_seed,
                "PPP incremental seed": input_incremental_seed,
                "PPP combinatorial": input_combinatorial,
            }
        )

        log(
            self.ppp_logger,
            self.ppp_debug_level,
            logging.INFO,
            f"Post-processing prompts ({'i2i' if is_i2i else 't2i'})",
        )
        env_info = {
            "app": app.value,
            "models_path": models_path,
            "model_filename": getattr(p.sd_model.sd_checkpoint_info, "filename", ""),
            "model_class": p.sd_model.__class__.__name__,
            "property_base": p.sd_model,
        }
        if app == SUPPORTED_APPS.forge:
            env_info["model_class"] = p.sd_model.model_config.__class__.__name__
        wc_wildcards_folders = getattr(opts, "ppp_wil_wildcardsfolders", "")
        if wc_wildcards_folders == "":
            wc_wildcards_folders = os.getenv("WILDCARD_DIR", PPPWildcards.DEFAULT_WILDCARDS_FOLDER)
        wildcards_folders = [
            (f if os.path.isabs(f) else os.path.abspath(os.path.join(models_path, f)))
            for f in wc_wildcards_folders.split(",")
            if f.strip() != ""
        ]
        en_mappings_folders = getattr(opts, "ppp_en_mappingsfolders", "")
        if en_mappings_folders == "":
            en_mappings_folders = os.getenv(
                "EXTRANETWORKMAPPINGS_DIR",
                PPPExtraNetworkMappings.DEFAULT_ENMAPPINGS_FOLDER,
            )
        enmappings_folders = [
            (f if os.path.isabs(f) else os.path.abspath(os.path.join(models_path, f)))
            for f in en_mappings_folders.split(",")
            if f.strip() != ""
        ]
        self.wildcards_obj.refresh_wildcards(
            self.ppp_debug_level, wildcards_folders if options.process_wildcards else None
        )
        self.extranetwork_mappings_obj.refresh_extranetwork_mappings(self.ppp_debug_level, enmappings_folders)
        ppp = PromptPostProcessor(
            self.ppp_logger,
            env_info,
            options,
            self.grammar_content,
            self.ppp_interrupt,
            self.wildcards_obj,
            self.extranetwork_mappings_obj,
        )
        hash_fullenv = hash(
            (ppp.envinfo_hash(), ppp.options_hash(), self.wildcards_obj, self.extranetwork_mappings_obj)
        )

        if input_force_equal_seeds:
            log(self.ppp_logger, self.ppp_debug_level, logging.INFO, "Forcing equal seeds")
            seeds: list[int] = getattr(p, "all_seeds", [])
            subseeds: list[int] = getattr(p, "all_subseeds", [])
            p.all_seeds = [seeds[0] for _ in seeds]
            p.all_subseeds = [subseeds[0] for _ in subseeds]

        calculated_seeds: list[int] = []
        if input_unlink_seed:
            log(self.ppp_logger, self.ppp_debug_level, logging.INFO, "Using unlinked seed")
            if input_incremental_seed:
                first_seed = np.random.randint(0, 2**32, dtype=np.int64) if input_seed == -1 else input_seed
                calculated_seeds = [first_seed + i for i in range(num_seeds)]
            elif input_seed == -1:
                calculated_seeds = np.random.randint(0, 2**32, size=num_seeds, dtype=np.int64)
            else:
                calculated_seeds = [input_seed for _ in range(num_seeds)]
        else:
            seeds: list[int] = getattr(p, "all_seeds", [])
            subseeds: list[int] = getattr(p, "all_subseeds", [])
            subseed_strength: float = getattr(p, "subseed_strength", 0.0)
            if subseed_strength > 0:
                calculated_seeds = [
                    int(subseed * subseed_strength + seed * (1 - subseed_strength))
                    for seed, subseed in zip(seeds, subseeds)
                ]
                # if len(set(calculated_seeds)) < len(calculated_seeds):
                #     self.ppp_logger.info("Adjusting seeds because some are equal.")
                #     calculated_seeds = [seed + i for i, seed in enumerate(calculated_seeds)]
            else:
                calculated_seeds = seeds

        # (prompt type, typeindex) -> (new positive prompt, new negative prompt)
        prompts_list: dict[tuple[str, int], tuple[str, str]] = {}
        extra_params = {}

        # adds prompts
        regular_type = "regular"
        rpr: list[str] = getattr(p, "all_prompts", None)
        rnr: list[str] = getattr(p, "all_negative_prompts", None)
        regular_exists = rpr is not None and rnr is not None
        hiresfix_type = "hiresfix"
        rph: list[str] = getattr(p, "all_hr_prompts", None)
        rnh: list[str] = getattr(p, "all_hr_negative_prompts", None)
        hiresfix_exists = rph is not None and rnh is not None
        for i in range(len(calculated_seeds)):
            if regular_exists:
                prompts_list[(regular_type, i)] = None
            if hiresfix_exists:
                prompts_list[(hiresfix_type, i)] = None

        if input_combinatorial:
            seed_for_comb = calculated_seeds[0] if calculated_seeds else 0
            regular_copy = (rpr.copy() if rpr else None, rnr.copy() if rnr else None)
            hiresfix_copy = (rph.copy() if rph else None, rnh.copy() if rnh else None)
            regular_changes = False
            hiresfix_changes = False
            if regular_exists:
                log(self.ppp_logger, self.ppp_debug_level, logging.INFO, "processing prompts combinatorially (regular)")
                comb_results = ppp.process_prompt(rpr[0], rnr[0], seed_for_comb)
                num_comb = len(comb_results)
                for i in range(len(rpr)):  # pylint: disable=consider-using-enumerate
                    posp, negp, _ = comb_results[i % num_comb]
                    prompts_list[(regular_type, i)] = (posp, negp)
                extra_params["PPP combination"] = [1+(i % num_comb) for i in range(len(rpr))]
            if hiresfix_exists:
                log(self.ppp_logger, self.ppp_debug_level, logging.INFO, "processing prompts combinatorially (hiresfix)")
                comb_results_hr = ppp.process_prompt(rph[0], rnh[0], seed_for_comb)
                num_comb_hr = len(comb_results_hr)
                for i in range(len(rph)):  # pylint: disable=consider-using-enumerate
                    posp, negp, _ = comb_results_hr[i % num_comb_hr]
                    prompts_list[(hiresfix_type, i)] = (posp, negp)
                extra_params["PPP HR combination"] = [1+(i % num_comb_hr) for i in range(len(rph))]
        else:
            # processes prompts
            for prompttype, typeindex in prompts_list.keys():
                log(self.ppp_logger, self.ppp_debug_level, logging.INFO, f"processing prompts ({prompttype}[{typeindex+1}])")
                key = (
                    (hash_fullenv, calculated_seeds[typeindex], rpr[typeindex], rnr[typeindex])
                    if prompttype == regular_type
                    else (hash_fullenv, calculated_seeds[typeindex], rph[typeindex], rnh[typeindex])
                )
                cached = self.lru_cache.get(key)
                if cached is None:
                    (hsh, seed, prompt, negative_prompt) = key
                    results = ppp.process_prompt(prompt, negative_prompt, seed)
                    posp, negp, _ = results[0]
                    cached = (posp, negp)
                    self.lru_cache.put(key, cached)
                    # adds also the result so i2i doesn't process it unnecessarily
                    self.lru_cache.put((hsh, seed, posp, negp), cached)
                else:
                    log(self.ppp_logger, self.ppp_debug_level, logging.INFO, "result already in cache")
                prompts_list[(prompttype, typeindex)] = cached

        # with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "last_prompts.txt"), "w", encoding="utf-8") as f:
        #     for (prompttype, typeindex), (posp, negp) in prompts_list.items():
        #         f.write(f"Key: {prompttype} {typeindex}\n")
        #         f.write(f"Seed: {calculated_seeds[typeindex]}\n")
        #         f.write(f"Old Positive: {rpr[typeindex] if prompttype == regular_type else rph[typeindex]}\n")
        #         f.write(f"Old Negative: {rnr[typeindex] if prompttype == regular_type else rnh[typeindex]}\n")
        #         f.write(f"New Positive: {posp}\n")
        #         f.write(f"New Negative: {negp}\n")
        #         f.write("\n")

        # updates the prompts
        regular_copy = (rpr.copy() if rpr else None, rnr.copy() if rnr else None)
        hiresfix_copy = (rph.copy() if rph else None, rnh.copy() if rnh else None)
        regular_changes = False
        hiresfix_changes = False
        for (prompttype, typeindex), (posp, negp) in prompts_list.items():
            if prompttype == regular_type:
                if rpr[typeindex].strip() != posp.strip() or rnr[typeindex].strip() != negp.strip():
                    regular_changes = True
                rpr[typeindex] = posp
                rnr[typeindex] = negp
            elif prompttype == hiresfix_type:
                if rph[typeindex].strip() != posp.strip() or rnh[typeindex].strip() != negp.strip():
                    hiresfix_changes = True
                rph[typeindex] = posp
                rnh[typeindex] = negp

        # initialize extra generation parameters
        if add_prompts:
            if regular_changes:
                extra_params["PPP original prompts"] = regular_copy[0]
                extra_params["PPP original negative prompts"] = regular_copy[1]
            if hiresfix_changes:
                extra_params["PPP original HR prompts"] = hiresfix_copy[0]
                extra_params["PPP original HR negative prompts"] = hiresfix_copy[1]

        # fill extra generation parameters only if not already present
        for k, v in extra_params.items():
            if p.extra_generation_params.get(k) is None:
                p.extra_generation_params[k] = v

        t2 = time.monotonic_ns()
        log(
            self.ppp_logger,
            self.ppp_debug_level,
            logging.INFO,
            f"process time: {(t2 - t1) / 1_000_000_000:.3f} seconds",
        )

    def ppp_interrupt(self):
        """
        Interrupts the generation.

        Returns:
            None
        """
        shared.state.interrupted = True


def on_ui_settings():
    """
    Callback function for UI settings.

    Returns:
        None
    """

    section = ("prompt-post-processor", PromptPostProcessor.NAME)

    def import_old_settings(names, default):
        for name in names:
            if hasattr(opts, name):
                return getattr(opts, name)
        return default

    def import_bool_to_any(name, value_false, value_true, default):
        if hasattr(opts, name):
            return value_true if getattr(opts, name) else value_false
        return default

    def new_html_title(title):
        info = shared.OptionInfo(
            title,
            "",
            gr.HTML,
            section=section,
        )
        info.do_not_save = True
        return info

    # general settings
    shared.opts.add_option(
        key="ppp_gen_sep",
        info=new_html_title("<h2>General settings</h2>"),
    )
    shared.opts.add_option(
        key="ppp_gen_debug_level",
        info=shared.OptionInfo(
            default=import_bool_to_any(
                "ppp_gen_debug",
                DEBUG_LEVEL.minimal.value,
                DEBUG_LEVEL.full.value,
                DEBUG_LEVEL.minimal.value,
            ),
            label="Debug level",
            component=gr.Radio,
            component_args={
                "choices": (
                    ("None", DEBUG_LEVEL.none.value),
                    ("Minimal", DEBUG_LEVEL.minimal.value),
                    ("Full", DEBUG_LEVEL.full.value),
                ),
            },
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_gen_onwarning",
        info=shared.OptionInfo(
            default=ONWARNING_CHOICES.warn.value,
            label="What to do on invalid content warnings",
            component=gr.Radio,
            component_args={
                "choices": (
                    ("Show warning in console", ONWARNING_CHOICES.warn.value),
                    ("Stop the generation", ONWARNING_CHOICES.stop.value),
                )
            },
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_gen_strict_operators",
        info=shared.OptionInfo(
            default=PromptPostProcessor.DEFAULT_STRICT_OPERATORS,
            label="Use strict operators",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_gen_doi2i",
        info=shared.OptionInfo(
            False,
            label="Apply in img2img",
            comment_after='<span class="info">(this includes any pass that contains an initial image, like adetailer)</span>',
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_gen_addpromptstometadata",
        info=shared.OptionInfo(
            True,
            label="Add original prompts to metadata (if they change)",
            section=section,
        ),
    )

    shared.opts.add_option(
        key="ppp_en_mappingsfolders",
        info=shared.OptionInfo(
            PPPExtraNetworkMappings.DEFAULT_ENMAPPINGS_FOLDER,
            label="Extranetwork Mappings folders",
            comment_after='<span class="info">(absolute or relative to the models folder)</span>',
            section=section,
        ),
    )

    # wildcard settings
    shared.opts.add_option(
        key="ppp_wil_sep",
        info=new_html_title("<br><h2>Wildcard settings</h2>"),
    )
    shared.opts.add_option(
        key="ppp_wil_processwildcards",
        info=shared.OptionInfo(
            True,
            label="Process wildcards",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_wil_wildcardsfolders",
        info=shared.OptionInfo(
            PPPWildcards.DEFAULT_WILDCARDS_FOLDER,
            label="Wildcards folders",
            comment_after='<span class="info">(absolute or relative to the models folder)</span>',
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_wil_ifwildcards",
        info=shared.OptionInfo(
            default=import_old_settings(
                ["ppp_gen_ifwildcards", "ppp_ifwildcards"],
                IFWILDCARDS_CHOICES.ignore.value,
            ),
            label="What to do with remaining/invalid wildcards?",
            component=gr.Radio,
            component_args={
                "choices": (
                    ("Ignore", IFWILDCARDS_CHOICES.ignore.value),
                    ("Remove", IFWILDCARDS_CHOICES.remove.value),
                    ("Add visible warning", IFWILDCARDS_CHOICES.warn.value),
                    ("Stop the generation", IFWILDCARDS_CHOICES.stop.value),
                )
            },
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_wil_choice_separator",
        info=shared.OptionInfo(
            PromptPostProcessor.DEFAULT_CHOICE_SEPARATOR,
            label="Default separator used when adding multiple choices",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_wil_keep_choices_order",
        info=shared.OptionInfo(
            False,
            label="Keep the order of selected choices",
            section=section,
        ),
    )

    # content removal settings
    shared.opts.add_option(
        key="ppp_rem_sep",
        info=new_html_title("<br><h2>Content removal settings</h2>"),
    )
    shared.opts.add_option(
        key="ppp_rem_removeextranetworktags",
        info=shared.OptionInfo(
            False,
            label="Remove extra network tags",
            section=section,
        ),
    )

    # send to negative settings
    shared.opts.add_option(
        key="ppp_stn_sep",
        info=new_html_title("<br><h2>Send to Negative settings</h2>"),
    )
    shared.opts.add_option(
        key="ppp_stn_separator",
        info=shared.OptionInfo(
            PromptPostProcessor.DEFAULT_STN_SEPARATOR,
            label="Separator used when adding to the negative prompt",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_stn_ignorerepeats",
        info=shared.OptionInfo(
            True,
            label="Ignore repeated content",
            section=section,
        ),
    )
    # clean-up settings
    shared.opts.add_option(
        key="ppp_cup_sep",
        info=new_html_title("<br><h2>Clean-up settings</h2>"),
    )
    shared.opts.add_option(
        key="ppp_cup_emptyconstructs",
        info=shared.OptionInfo(
            True,
            label="Remove empty constructs (attention, alternation, scheduling)",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_cup_extraseparators",
        info=shared.OptionInfo(
            True,
            label="Remove extra separators",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_cup_extraseparators2",
        info=shared.OptionInfo(
            True,
            label="Remove additional extra separators",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_cup_extraseparators_include_eol",
        info=shared.OptionInfo(
            False,
            label="The extra separators options also remove EOLs",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_cup_breaks",
        info=shared.OptionInfo(
            True,
            label="Clean up around BREAKs",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_cup_breaks_eol",
        info=shared.OptionInfo(
            False,
            label="Use EOL instead of Space before BREAKs",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_cup_ands",
        info=shared.OptionInfo(
            True,
            label="Clean up around ANDs",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_cup_ands_eol",
        info=shared.OptionInfo(
            False,
            label="Use EOL instead of Space before ANDs",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_cup_extranetworktags",
        info=shared.OptionInfo(
            False,
            label="Clean up around extra network tags",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_cup_extraspaces",
        info=shared.OptionInfo(
            True,
            label="Remove extra spaces",
            section=section,
        ),
    )
    shared.opts.add_option(
        key="ppp_cup_mergeattention",
        info=shared.OptionInfo(
            True,
            label="Merge attention modifiers (weights) when possible",
            section=section,
        ),
    )

    # Remove old settings
    # for name in ["ppp_gen_ifwildcards", "ppp_ifwildcards", "ppp_gen_debug", "ppp_stn_doi2i", "ppp_cup_doi2i"]:
    #     if hasattr(opts, name):
    #         delattr(opts, name)


script_callbacks.on_ui_settings(on_ui_settings)
