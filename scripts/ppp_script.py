if __name__ == "__main__":
    raise SystemExit("This script must be run from a Stable Diffusion WebUI")

import sys
import os
import time
import numpy as np

sys.path.append(os.path.join(os.path.realpath(__file__), ".."))  # base path for the extension

from modules import scripts, shared, script_callbacks  # pylint: disable=import-error
from modules.processing import StableDiffusionProcessing  # pylint: disable=import-error
from modules.shared import opts  # pylint: disable=import-error
from modules.paths import models_path  # pylint: disable=import-error
import gradio as gr  # pylint: disable=import-error
from ppp import PromptPostProcessor  # pylint: disable=import-error
from ppp_logging import DEBUG_LEVEL, PromptPostProcessorLogFactory  # pylint: disable=import-error
from ppp_cache import PPPLRUCache  # pylint: disable=import-error
from ppp_wildcards import PPPWildcards  # pylint: disable=import-error


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

    @classmethod
    def get_instance_count(cls):
        return cls.instance_count

    def __init__(self):
        """
        Initializes the PromptPostProcessor object.

        This method adds callbacks for UI settings and initializes the logger.

        Parameters:
            None

        Returns:
            None
        """
        self.increment_instance_count()
        lf = PromptPostProcessorLogFactory()
        self.name = PromptPostProcessor.NAME
        self.ppp_logger = lf.log
        self.ppp_debug_level = DEBUG_LEVEL(getattr(opts, "ppp_gen_debug_level", DEBUG_LEVEL.none.value))
        self.lru_cache = PPPLRUCache(1000, logger=self.ppp_logger, debug_level=self.ppp_debug_level)
        grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../grammar.lark")
        with open(grammar_filename, "r", encoding="utf-8") as file:
            self.grammar_content = file.read()
        self.wildcards_obj = PPPWildcards(lf.log)
        i = self.get_instance_count()
        if i == 1:  # some UIs create multiple instances
            self.ppp_logger.info(f"{PromptPostProcessor.NAME} {PromptPostProcessor.VERSION} initialized")

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
        return [force_equal_seeds, unlink_seed, seed, incremental_seed]

    def process(
        self,
        p: StableDiffusionProcessing,
        input_force_equal_seeds,
        input_unlink_seed,
        input_seed,
        input_incremental_seed,
    ):  # pylint: disable=arguments-differ
        """
        Processes the prompts and applies post-processing operations.

        Args:
            p (StableDiffusionProcessing): The StableDiffusionProcessing object containing the prompts.
            input_force_equal_seeds (bool): Flag indicating whether to force equal seeds.
            input_unlink_seed (bool): Flag indicating whether to unlink the seed.
            input_seed (int): The seed value.
            input_incremental_seed (bool): Flag indicating whether to use incremental seed.

        Returns:
            None
        """
        t1 = time.time()
        if getattr(opts, "prompt_attention", "") == "Compel parser":
            self.ppp_logger.warning("Compel parser is not supported!")
        init_images = getattr(p, "init_images", [None]) or [None]
        is_i2i = bool(init_images[0])
        self.ppp_debug_level = DEBUG_LEVEL(getattr(opts, "ppp_gen_debug_level", DEBUG_LEVEL.none.value))
        do_i2i = getattr(opts, "ppp_gen_doi2i", False)
        add_prompts = getattr(opts, "ppp_gen_addpromptstometadata", True)
        if is_i2i and not do_i2i:
            if self.ppp_debug_level != DEBUG_LEVEL.none:
                self.ppp_logger.info("Not processing the prompt for i2i")
            return

        p.extra_generation_params.update(
            {
                "PPP force equal seeds": input_force_equal_seeds,
                "PPP unlink seed": input_unlink_seed,
                "PPP prompt seed": input_seed,
                "PPP incremental seed": input_incremental_seed,
            }
        )

        app_names = {
            "sdnext": "SD.Next",
            "forge": "Forge",
            "reforge": "reForge",
            "a1111": "A1111 (or compatible)",
        }
        app = (
            "forge"
            if hasattr(p.sd_model, "model_config")
            else (
                "reforge"
                if hasattr(p.sd_model, "forge_objects")
                else ("sdnext" if hasattr(p.sd_model, "is_sdxl") and not hasattr(p.sd_model, "is_ssd") else "a1111")
            )
        )
        if self.ppp_debug_level != DEBUG_LEVEL.none:
            self.ppp_logger.info(f"Post-processing prompts ({'i2i' if is_i2i else 't2i'}) running on {app_names[app]}")
        models_supported = {x: True for x in PromptPostProcessor.SUPPORTED_MODELS}
        if app == "sdnext":
            models_supported["ssd"] = False
        elif app == "forge":
            models_supported["ssd"] = False
            models_supported["auraflow"] = False
        elif app == "reforge":
            models_supported["flux"] = False
            models_supported["auraflow"] = False
        else:  # assume A1111 compatible
            models_supported["flux"] = False
            models_supported["auraflow"] = False
        env_info = {
            "app": app,
            "models_path": models_path,
            "model_filename": getattr(p.sd_model.sd_checkpoint_info, "filename", ""),
            "model_class": "",
            "is_sd1": False,  # Stable Diffusion 1
            "is_sd2": False,  # Stable Diffusion 2
            "is_sdxl": False,  # Stable Diffusion XL
            "is_ssd": False,  # Segmind Stable Diffusion 1B
            "is_sd3": False,  # Stable Diffusion 3
            "is_flux": False,  # Flux
            "is_auraflow": False,  # AuraFlow
            "is_pixart": False,  # PixArt
            "is_lumina2": False,  # Lumina2
            "is_ltxv": False,  # LTXV
            "is_cosmos": False,  # Cosmos
            "is_genmomochi": False,  # GenmoMochi
            "is_hunyuan": False,  # Hunyuan
            "is_hunyuanvideo": False,  # HunyuanVideo
            "is_hunyuan3d": False,  # Hunyuan3D
            "is_wanvideo": False,  # WanVideo
            "is_hidream": False,  # HiDream
        }
        if app == "sdnext":
            # cannot differentiate SD1 and SD2, we set True to both
            # LatentDiffusion is for the original backend, StableDiffusionPipeline is for the diffusers backend
            env_info["model_class"] = p.sd_model.__class__.__name__
            env_info["is_sd1"] = p.sd_model.__class__.__name__ in ("LatentDiffusion", "StableDiffusionPipeline")
            env_info["is_sd2"] = p.sd_model.__class__.__name__ in ("LatentDiffusion", "StableDiffusionPipeline")
            env_info["is_sdxl"] = p.sd_model.__class__.__name__ == "StableDiffusionXLPipeline"
            env_info["is_ssd"] = False  # ?
            env_info["is_sd3"] = p.sd_model.__class__.__name__ == "StableDiffusion3Pipeline"
            env_info["is_flux"] = p.sd_model.__class__.__name__ == "FluxPipeline"
            env_info["is_auraflow"] = p.sd_model.__class__.__name__ == "AuraFlowPipeline"
            # also supports 'Latent Consistency Model': LatentConsistencyModelPipeline', 'PixArt-Alpha': 'PixArtAlphaPipeline', 'UniDiffuser': 'UniDiffuserPipeline', 'Wuerstchen': 'WuerstchenCombinedPipeline', 'Kandinsky 2.1': 'KandinskyPipeline', 'Kandinsky 2.2': 'KandinskyV22Pipeline', 'Kandinsky 3': 'Kandinsky3Pipeline', 'DeepFloyd IF': 'IFPipeline', 'Custom Diffusers Pipeline': 'DiffusionPipeline', 'InstaFlow': 'StableDiffusionPipeline', 'SegMoE': 'StableDiffusionPipeline', 'Kolors': 'KolorsPipeline', 'AuraFlow': 'AuraFlowPipeline', 'CogView': 'CogView3PlusPipeline'
        elif app == "forge":
            # from repositories\huggingface_guess\huggingface_guess\model_list.py
            env_info["model_class"] = p.sd_model.model_config.__class__.__name__
            env_info["is_sd1"] = getattr(p.sd_model, "is_sd1", False)
            env_info["is_sd2"] = getattr(p.sd_model, "is_sd2", False)
            env_info["is_sdxl"] = getattr(p.sd_model, "is_sdxl", False)
            env_info["is_ssd"] = False  # ?
            env_info["is_sd3"] = getattr(
                p.sd_model, "is_sd3", False
            )  # p.sd_model.model_config.__class__.__name__ == "SD3" # not actually supported?
            env_info["is_flux"] = p.sd_model.model_config.__class__.__name__ in ("Flux", "FluxSchnell")
            env_info["is_auraflow"] = False  # p.sd_model.model_config.__class__.__name__ == "AuraFlow" # not supported
        elif app == "reforge":
            env_info["model_class"] = p.sd_model.__class__.__name__
            env_info["is_sd1"] = getattr(p.sd_model, "is_sd1", False)
            env_info["is_sd2"] = getattr(p.sd_model, "is_sd2", False)
            env_info["is_sdxl"] = getattr(p.sd_model, "is_sdxl", False)
            env_info["is_ssd"] = getattr(p.sd_model, "is_ssd", False)
            env_info["is_sd3"] = getattr(p.sd_model, "is_sd3", False)
            env_info["is_flux"] = False
            env_info["is_auraflow"] = False
        else:  # assume A1111 compatible (p.sd_model.__class__.__name__=="DiffusionEngine")
            env_info["model_class"] = p.sd_model.__class__.__name__
            env_info["is_sd1"] = getattr(p.sd_model, "is_sd1", False)
            env_info["is_sd2"] = getattr(p.sd_model, "is_sd2", False)
            env_info["is_sdxl"] = getattr(p.sd_model, "is_sdxl", False)
            env_info["is_ssd"] = getattr(p.sd_model, "is_ssd", False)
            env_info["is_sd3"] = getattr(p.sd_model, "is_sd3", False)
            env_info["is_flux"] = False
            env_info["is_auraflow"] = False
        wc_wildcards_folders = getattr(opts, "ppp_wil_wildcardsfolders", "")
        if wc_wildcards_folders == "":
            wc_wildcards_folders = os.getenv("WILDCARD_DIR", PPPWildcards.DEFAULT_WILDCARDS_FOLDER)
        wildcards_folders = [
            (f if os.path.isabs(f) else os.path.abspath(os.path.join(models_path, f)))
            for f in wc_wildcards_folders.split(",")
            if f.strip() != ""
        ]
        options = {
            "debug_level": getattr(opts, "ppp_gen_debug_level", DEBUG_LEVEL.none.value),
            "variants_definitions": getattr(
                opts, "ppp_gen_variantsdefinitions", PromptPostProcessor.DEFAULT_VARIANTS_DEFINITIONS
            ),
            "process_wildcards": getattr(opts, "ppp_wil_processwildcards", True),
            "if_wildcards": getattr(opts, "ppp_wil_ifwildcards", PromptPostProcessor.IFWILDCARDS_CHOICES.stop.value),
            "choice_separator": getattr(opts, "ppp_wil_choice_separator", PromptPostProcessor.DEFAULT_CHOICE_SEPARATOR),
            "keep_choices_order": getattr(opts, "ppp_wil_keep_choices_order", False),
            "stn_separator": getattr(opts, "ppp_stn_separator", PromptPostProcessor.DEFAULT_STN_SEPARATOR),
            "stn_ignore_repeats": getattr(opts, "ppp_stn_ignorerepeats", True),
            "cleanup_extra_spaces": getattr(opts, "ppp_cup_extraspaces", True),
            "cleanup_empty_constructs": getattr(opts, "ppp_cup_emptyconstructs", True),
            "cleanup_extra_separators": getattr(opts, "ppp_cup_extraseparators", True),
            "cleanup_extra_separators2": getattr(opts, "ppp_cup_extraseparators2", True),
            "cleanup_breaks": getattr(opts, "ppp_cup_breaks", True),
            "cleanup_breaks_eol": getattr(opts, "ppp_cup_breaks_eol", False),
            "cleanup_ands": getattr(opts, "ppp_cup_ands", True),
            "cleanup_ands_eol": getattr(opts, "ppp_cup_ands_eol", False),
            "cleanup_extranetwork_tags": getattr(opts, "ppp_cup_extranetworktags", False),
            "cleanup_merge_attention": getattr(opts, "ppp_cup_mergeattention", True),
            "remove_extranetwork_tags": getattr(opts, "ppp_rem_removeextranetworktags", False),
        }
        self.wildcards_obj.refresh_wildcards(
            self.ppp_debug_level, wildcards_folders if options["process_wildcards"] else None
        )
        ppp = PromptPostProcessor(
            self.ppp_logger, self.ppp_interrupt, env_info, options, self.grammar_content, self.wildcards_obj
        )
        prompts_list = []

        if input_force_equal_seeds:
            if self.ppp_debug_level != DEBUG_LEVEL.none:
                self.ppp_logger.info("Forcing equal seeds")
            seeds = getattr(p, "all_seeds", [])
            subseeds = getattr(p, "all_subseeds", [])
            p.all_seeds = [seeds[0] for _ in seeds]
            p.all_subseeds = [subseeds[0] for _ in subseeds]

        if input_unlink_seed:
            if self.ppp_debug_level != DEBUG_LEVEL.none:
                self.ppp_logger.info("Using unlinked seed")
            num_seeds = len(getattr(p, "all_seeds", []))
            if input_incremental_seed:
                first_seed = np.random.randint(0, 2**32, dtype=np.int64) if input_seed == -1 else input_seed
                calculated_seeds = [first_seed + i for i in range(num_seeds)]
            elif input_seed == -1:
                calculated_seeds = np.random.randint(0, 2**32, size=num_seeds, dtype=np.int64)
            else:
                calculated_seeds = [input_seed for _ in range(num_seeds)]
        else:
            seeds = getattr(p, "all_seeds", [])
            subseeds = getattr(p, "all_subseeds", [])
            subseed_strength = getattr(p, "subseed_strength", 0.0)
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

        # initialize extra generation parameters
        extra_params = {}

        # adds regular prompts
        rpr: list[str] = getattr(p, "all_prompts", None)
        rnr: list[str] = getattr(p, "all_negative_prompts", None)
        if rpr is not None and rnr is not None:
            if add_prompts:
                extra_params.update(
                    {
                        "PPP original prompts": rpr.copy(),
                        "PPP original negative prompts": rnr.copy(),
                    }
                )
            prompts_list += [
                ("regular", seed, prompt, negative_prompt)
                for seed, prompt, negative_prompt in zip(calculated_seeds, rpr, rnr)
                if (seed, prompt, negative_prompt) not in prompts_list
            ]
        # make it compatible with A1111 hires fix
        rph: list[str] = getattr(p, "all_hr_prompts", None)
        rnh: list[str] = getattr(p, "all_hr_negative_prompts", None)
        if rph is not None and rnh is not None:
            if add_prompts:
                extra_params.update(
                    {
                        "PPP original HR prompts": rph.copy(),
                        "PPP original HR negative prompts": rnh.copy(),
                    }
                )
            prompts_list += [
                ("hiresfix", seed, prompt, negative_prompt)
                for seed, prompt, negative_prompt in zip(calculated_seeds, rph, rnh)
                if (seed, prompt, negative_prompt) not in prompts_list
            ]

        # fill extra generation parameters only if not already present
        for k, v in extra_params.items():
            if p.extra_generation_params.get(k) is None:
                p.extra_generation_params[k] = v

        # processes prompts
        for i, (prompttype, seed, prompt, negative_prompt) in enumerate(prompts_list):
            if self.ppp_debug_level != DEBUG_LEVEL.none:
                self.ppp_logger.info(f"processing prompts[{i+1}] ({prompttype})")
            if self.lru_cache.get((seed, hash(self.wildcards_obj), prompt, negative_prompt)) is None:
                posp, negp, _ = ppp.process_prompt(prompt, negative_prompt, seed)
                self.lru_cache.put((seed, hash(self.wildcards_obj), prompt, negative_prompt), (posp, negp))
                # adds also the result so i2i doesn't process it unnecessarily
                self.lru_cache.put((seed, hash(self.wildcards_obj), posp, negp), (posp, negp))
            elif self.ppp_debug_level != DEBUG_LEVEL.none:
                self.ppp_logger.info("result already in cache")

        # updates the prompts
        if rpr is not None and rnr is not None:
            for i, (seed, prompt, negative_prompt) in enumerate(zip(calculated_seeds, rpr, rnr)):
                found = self.lru_cache.get((seed, hash(self.wildcards_obj), prompt, negative_prompt))
                if found is not None:
                    rpr[i] = found[0]
                    rnr[i] = found[1]
        if rph is not None and rnh is not None:
            for i, (seed, prompt, negative_prompt) in enumerate(zip(calculated_seeds, rph, rnh)):
                found = self.lru_cache.get((seed, hash(self.wildcards_obj), prompt, negative_prompt))
                if found is not None:
                    rph[i] = found[0]
                    rnh[i] = found[1]

        t2 = time.time()
        if self.ppp_debug_level != DEBUG_LEVEL.none:
            self.ppp_logger.info(f"process time: {t2 - t1:.3f} seconds")

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
        key="ppp_gen_variantsdefinitions",
        info=shared.OptionInfo(
            PromptPostProcessor.DEFAULT_VARIANTS_DEFINITIONS,
            label="Definitions for variant models",
            comment_after="Recognized based on strings found in the full filename. Format for each line is: 'name(kind)=comma separated list of substrings (case insensitive)' with kind being one of the base model types ("
            + ",".join(PromptPostProcessor.SUPPORTED_MODELS)
            + ") or not specified.",
            component=gr.Textbox,
            component_args={"lines": 7},
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
            label="Add original prompts to metadata",
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
                PromptPostProcessor.IFWILDCARDS_CHOICES.ignore.value,
            ),
            label="What to do with remaining/invalid wildcards?",
            component=gr.Radio,
            component_args={
                "choices": (
                    ("Ignore", PromptPostProcessor.IFWILDCARDS_CHOICES.ignore.value),
                    ("Remove", PromptPostProcessor.IFWILDCARDS_CHOICES.remove.value),
                    ("Add visible warning", PromptPostProcessor.IFWILDCARDS_CHOICES.warn.value),
                    ("Stop the generation", PromptPostProcessor.IFWILDCARDS_CHOICES.stop.value),
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
