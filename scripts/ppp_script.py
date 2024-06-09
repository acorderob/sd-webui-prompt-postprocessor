if __name__ == "__main__":
    raise SystemExit("This script must be run from a Stable Diffusion WebUI")

import sys
import os
import time

sys.path.append(os.path.join(sys.path[0], ".."))


from modules import scripts, shared, script_callbacks
from modules.processing import StableDiffusionProcessing
from modules.shared import opts
from modules.paths import models_path
import gradio as gr
from ppp import PromptPostProcessor
from ppp_logging import DEBUG_LEVEL, PromptPostProcessorLogFactory
from ppp_cache import PPPLRUCache
from ppp_wildcards import PPPWildcards


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

    def __init__(self):
        """
        Initializes the PromptPostProcessor object.

        This method adds callbacks for UI settings and initializes the logger.

        Parameters:
            None

        Returns:
            None
        """
        lf = PromptPostProcessorLogFactory()
        self.name = PromptPostProcessor.NAME
        self.ppp_logger = lf.log
        self.ppp_debug_level = DEBUG_LEVEL(getattr(opts, "ppp_gen_debug_level", DEBUG_LEVEL.none.value))
        self.lru_cache = PPPLRUCache(1000)
        grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../grammar.lark")
        with open(grammar_filename, "r", encoding="utf-8") as file:
            self.grammar_content = file.read()
        self.wildcards_obj = PPPWildcards(lf.log)

    def title(self):
        """
        Returns the title of the script.

        Returns:
            str: The title of the script.
        """
        return PromptPostProcessor.NAME

    def show(self, is_img2img):
        """
        Determines whether the script should be shown based on the kind of processing.

        Args:
            is_img2img (bool): Flag indicating whether the processing is image-to-image.

        Returns:
            scripts.Visibility: The visibility setting for the script.
        """
        return scripts.AlwaysVisible

    def process(self, p: StableDiffusionProcessing, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Processes the prompts and applies post-processing operations.

        Args:
            p (StableDiffusionProcessing): The StableDiffusionProcessing object containing the prompts.

        Returns:
            None
        """
        t1 = time.time()
        if getattr(opts, "prompt_attention", "") == "Compel parser":
            self.ppp_logger.warning("Compel parser is not supported!")
        is_i2i = getattr(p, "init_images", [None])[0] is not None
        self.ppp_debug_level = DEBUG_LEVEL(getattr(opts, "ppp_gen_debug_level", DEBUG_LEVEL.none.value))
        do_i2i = getattr(opts, "ppp_gen_doi2i", False)
        if is_i2i and not do_i2i:
            if self.ppp_debug_level != DEBUG_LEVEL.none:
                self.ppp_logger.info("Not processing the prompt for i2i")
            return
        if self.ppp_debug_level != DEBUG_LEVEL.none:
            self.ppp_logger.info(f"Post-processing prompts ({'i2i' if is_i2i else 't2i'})")
        model_info = {
            "models_path": models_path,
            "model_filename": getattr(p.sd_model.sd_checkpoint_info, "filename", ""),  # path is absolute
            "is_sd1": False,  # Stable Diffusion 1
            "is_sd2": False,  # Stable Diffusion 2
            "is_sdxl": False,  # Stable Diffusion XL
            "is_ssd": False,  # Segmind Stable Diffusion 1B
            "is_sd3": False,  # Stable Diffusion 3
            "is_flux": False,  # Flux
        }
        app = (
            "forge"
            if hasattr(p.sd_model, "model_config")
            else "sdnext" if hasattr(p.sd_model, "is_sdxl") and not hasattr(p.sd_model, "is_ssd") else "a1111"
        )
        if app == "sdnext":
            # cannot differenciate SD1 and SD2, we set True to both
            # LatentDiffusion is for the original backend, StableDiffusionPipeline is for the diffusers backend
            model_info["is_sd1"] = p.sd_model.__class__.__name__ in ("LatentDiffusion", "StableDiffusionPipeline")
            model_info["is_sd2"] = p.sd_model.__class__.__name__ in ("LatentDiffusion", "StableDiffusionPipeline")
            model_info["is_sdxl"] = p.sd_model.__class__.__name__ == "StableDiffusionXLPipeline"
            model_info["is_ssd"] = False  # ?
            model_info["is_sd3"] = p.sd_model.__class__.__name__ == "StableDiffusion3Pipeline"
            model_info["is_flux"] = False
        elif app == "forge":
            model_info["is_sd1"] = getattr(p.sd_model, "is_sd1", False)
            model_info["is_sd2"] = getattr(p.sd_model, "is_sd2", False)
            model_info["is_sdxl"] = getattr(p.sd_model, "is_sdxl", False)
            model_info["is_ssd"] = False  # ?
            model_info["is_sd3"] = getattr(p.sd_model, "is_sd3", False)
            model_info["is_flux"] = p.sd_model.model_config.__class__.__name__ == "Flux"
        else:  # assume A1111 compatible (p.sd_model.__class__.__name__=="DiffusionEngine")
            model_info["is_sd1"] = getattr(p.sd_model, "is_sd1", False)
            model_info["is_sd2"] = getattr(p.sd_model, "is_sd2", False)
            model_info["is_sdxl"] = getattr(p.sd_model, "is_sdxl", False)
            model_info["is_ssd"] = getattr(p.sd_model, "is_ssd", False)
            model_info["is_sd3"] = getattr(p.sd_model, "is_sd3", False)
            model_info["is_flux"] = False
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
            "pony_substrings": getattr(opts, "ppp_gen_ponysubstrings", PromptPostProcessor.DEFAULT_PONY_SUBSTRINGS),
            "process_wildcards": getattr(opts, "ppp_wil_process_wildcards", True),
            "if_wildcards": getattr(opts, "ppp_wil_ifwildcards", PromptPostProcessor.IFWILDCARDS_CHOICES.ignore.value),
            "choice_separator": getattr(opts, "ppp_wil_choice_separator", PromptPostProcessor.DEFAULT_CHOICE_SEPARATOR),
            "keep_choices_order": getattr(opts, "ppp_wil_keep_choices_order", False),
            "stn_separator": getattr(opts, "ppp_stn_separator", PromptPostProcessor.DEFAULT_STN_SEPARATOR),
            "stn_ignore_repeats": getattr(opts, "ppp_stn_ignorerepeats", True),
            "stn_join_attention": getattr(opts, "ppp_stn_joinattention", True),
            "cleanup_extra_spaces": getattr(opts, "ppp_cup_extraspaces", True),
            "cleanup_empty_constructs": getattr(opts, "ppp_cup_emptyconstructs", True),
            "cleanup_extra_separators": getattr(opts, "ppp_cup_extraseparators", True),
            "cleanup_extra_separators2": getattr(opts, "ppp_cup_extraseparators2", True),
            "cleanup_breaks": getattr(opts, "ppp_cup_breaks", True),
            "cleanup_breaks_eol": getattr(opts, "ppp_cup_breaks_eol", False),
            "cleanup_ands": getattr(opts, "ppp_cup_ands", True),
            "cleanup_ands_eol": getattr(opts, "ppp_cup_ands_eol", False),
            "cleanup_extranetwork_tags": getattr(opts, "ppp_cup_extranetworktags", False),
            "remove_extranetwork_tags": getattr(opts, "ppp_rem_removeextranetworktags", False),
        }
        self.wildcards_obj.refresh_wildcards(
            self.ppp_debug_level, wildcards_folders if options["process_wildcards"] else None
        )
        ppp = PromptPostProcessor(
            self.ppp_logger, self.ppp_interrupt, model_info, options, self.grammar_content, self.wildcards_obj
        )
        prompts_list = []

        seeds = getattr(p, "all_seeds", [])
        subseeds = getattr(p, "all_subseeds", [])
        subseed_strength = getattr(p, "subseed_strength", 0.0)
        if subseed_strength > 0:
            calculated_seeds = [
                int(subseed * subseed_strength + seed * (1 - subseed_strength))
                for seed, subseed in zip(seeds, subseeds)
            ]
        else:
            calculated_seeds = seeds
        if len(set(calculated_seeds)) < len(calculated_seeds):
            self.ppp_logger.info("Adjusting seeds because some are equal.")
            calculated_seeds = [seed + i for i, seed in enumerate(calculated_seeds)]

        # adds regular prompts
        rpr = getattr(p, "all_prompts", None)
        rnr = getattr(p, "all_negative_prompts", None)
        if rpr is not None and rnr is not None:
            prompts_list += [
                ("regular", seed, prompt, negative_prompt)
                for seed, prompt, negative_prompt in zip(calculated_seeds, rpr, rnr)
                if (seed, prompt, negative_prompt) not in prompts_list
            ]
        # make it compatible with A1111 hires fix
        rph = getattr(p, "all_hr_prompts", None)
        rnh = getattr(p, "all_hr_negative_prompts", None)
        if rph is not None and rnh is not None:
            prompts_list += [
                ("hiresfix", seed, prompt, negative_prompt)
                for seed, prompt, negative_prompt in zip(calculated_seeds, rph, rnh)
                if (seed, prompt, negative_prompt) not in prompts_list
            ]

        # processes prompts
        for i, (prompttype, seed, prompt, negative_prompt) in enumerate(prompts_list):
            if self.ppp_debug_level != DEBUG_LEVEL.none:
                self.ppp_logger.info(f"processing prompts[{i+1}] ({prompttype})")
            if self.lru_cache.get((seed, prompt, negative_prompt)) is None:
                pp, np = ppp.process_prompt(prompt, negative_prompt, seed)
                self.lru_cache.put((seed, prompt, negative_prompt), (pp, np))
                # adds also the result so i2i doesn't process it unnecessarily
                self.lru_cache.put((seed, pp, np), (pp, np))
            elif self.ppp_debug_level != DEBUG_LEVEL.none:
                self.ppp_logger.info("result already in cache")

        # updates the prompts
        if rpr is not None and rnr is not None:
            for i, (seed, prompt, negative_prompt) in enumerate(zip(calculated_seeds, rpr, rnr)):
                found = self.lru_cache.get((seed, prompt, negative_prompt))
                if found is not None:
                    rpr[i] = found[0]
                    rnr[i] = found[1]
        if rph is not None and rnh is not None:
            for i, (seed, prompt, negative_prompt) in enumerate(zip(calculated_seeds, rph, rnh)):
                found = self.lru_cache.get((seed, prompt, negative_prompt))
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
        key="ppp_gen_ponysubstrings",
        info=shared.OptionInfo(
            PromptPostProcessor.DEFAULT_PONY_SUBSTRINGS,
            label="Comma separated list of substrings to look for in the model full filename to flag it as Pony (case insensitive)",
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

    # wildcard settings
    shared.opts.add_option(
        key="ppp_wil_sep",
        info=new_html_title('<br><h2>Wildcard settings</h2>'),
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
        info=new_html_title('<br><h2>Content removal settings</h2>'),
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
        info=new_html_title('<br><h2>Send to Negative settings</h2>'),
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
    shared.opts.add_option(
        key="ppp_stn_joinattention",
        info=shared.OptionInfo(
            True,
            label="Join attention modifiers (weights) when possible",
            section=section,
        ),
    )
    # clean-up settings
    shared.opts.add_option(
        key="ppp_cup_sep",
        info=new_html_title('<br><h2>Clean-up settings</h2>'),
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

    # Remove old settings
    # for name in ["ppp_gen_ifwildcards", "ppp_ifwildcards", "ppp_gen_debug", "ppp_stn_doi2i", "ppp_cup_doi2i"]:
    #     if hasattr(opts, name):
    #         delattr(opts, name)


script_callbacks.on_ui_settings(on_ui_settings)
