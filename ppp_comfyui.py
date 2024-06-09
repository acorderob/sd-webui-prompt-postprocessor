# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring, invalid-name

import os

# pylint: disable=import-error
import folder_paths  # type: ignore
import nodes  # type: ignore

from .ppp import PromptPostProcessor
from .ppp_logging import DEBUG_LEVEL, PromptPostProcessorLogFactory
from .ppp_wildcards import PPPWildcards

if __name__ == "__main__":
    raise SystemExit("This script must be run from ComfyUI")


class PromptPostProcessorComfyUINode:

    VERSION = PromptPostProcessor.VERSION

    logger = None

    def __init__(self):
        lf = PromptPostProcessorLogFactory()
        self.logger = lf.log
        grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "grammar.lark")
        with open(grammar_filename, "r", encoding="utf-8") as file:
            self.grammar_content = file.read()
        self.wildcards_obj = PPPWildcards(lf.log)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": (
                    "MODEL",
                    {
                        "forceInput": True,
                    },
                ),
                "modelname": (
                    "STRING",
                    {
                        "default": "",
                        "forceInput": True,
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": None,
                        "forceInput": False,
                    },
                ),
                "pos_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "forceInput": True,
                    },
                ),
                "neg_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "forceInput": True,
                    },
                ),
            },
            "optional": {
                "debug_level": (
                    [e.value for e in DEBUG_LEVEL],
                    {
                        "default": DEBUG_LEVEL.minimal.value,
                        "tooltip": "Debug level",
                    },
                ),
                "pony_substrings": (
                    "STRING",
                    {
                        "default": PromptPostProcessor.DEFAULT_PONY_SUBSTRINGS,
                        "placeholder": "comma separated list",
                        "tooltip": "Comma separated list of substrings to look for in the modelname to determine if the model is a pony model",
                    },
                ),
                "wc_process_wildcards": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Process wildcards in the prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "wc_wildcards_folders": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Comma separated list of wildcards folders",
                    },
                ),
                "wc_if_wildcards": (
                    [e.value for e in PromptPostProcessor.IFWILDCARDS_CHOICES],
                    {
                        "default": PromptPostProcessor.IFWILDCARDS_CHOICES.ignore.value,
                        "tooltip": "How to handle invalid wildcards in the prompt",
                    },
                ),
                "wc_choice_separator": (
                    "STRING",
                    {
                        "default": PromptPostProcessor.DEFAULT_CHOICE_SEPARATOR,
                        "tooltip": "Default separator for selected choices",
                    },
                ),
                "wc_keep_choices_order": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Keep the order of the choices in the prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "stn_separator": (
                    "STRING",
                    {
                        "default": PromptPostProcessor.DEFAULT_STN_SEPARATOR,
                        "tooltip": "Separator for the content added to the negative prompt",
                    },
                ),
                "stn_ignore_repeats": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Ignore repeated content added to the negative prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "stn_join_attention": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Merge attention in the content added to the negative prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_extra_spaces": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove extra spaces",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_empty_constructs": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove empty constructs",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_extra_separators": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove extra separators",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_extra_separators2": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove extra separators (additional cases)",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_breaks": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Cleanup around BREAKs",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_breaks_eol": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Set BREAKs in their own line",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_ands": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Cleanup around ANDs",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_ands_eol": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Set ANDs in their own line",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_extranetwork_tags": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Clean up around extra network tags",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "remove_extranetwork_tags": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Remove extra network tags",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
            },
        }

    RETURN_TYPES = (
        "STRING",
        "STRING",
    )
    RETURN_NAMES = (
        "pos_prompt",
        "neg_prompt",
    )

    FUNCTION = "process"

    CATEGORY = "ACB"

    @classmethod
    def IS_CHANGED(
        cls,
        model,
        modelname,
        pos_prompt,
        neg_prompt,
        seed,
        debug_level,  # pylint: disable=unused-argument
        pony_substrings,
        wc_process_wildcards,
        wc_wildcards_folders,
        wc_if_wildcards,
        wc_choice_separator,
        wc_keep_choices_order,
        stn_separator,
        stn_ignore_repeats,
        stn_join_attention,
        cleanup_extra_spaces,
        cleanup_empty_constructs,
        cleanup_extra_separators,
        cleanup_extra_separators2,
        cleanup_breaks,
        cleanup_breaks_eol,
        cleanup_ands,
        cleanup_ands_eol,
        cleanup_extranetwork_tags,
        remove_extranetwork_tags,
    ):
        new_run = {
            "model": model,
            "modelname": modelname,
            "pos_prompt": pos_prompt,
            "neg_prompt": neg_prompt,
            "seed": seed,
            "pony_substrings": pony_substrings,
            "process_wildcards": wc_process_wildcards,
            "wildcards_folders": wc_wildcards_folders,
            "if_wildcards": wc_if_wildcards,
            "choice_separator": wc_choice_separator,
            "keep_choices_order": wc_keep_choices_order,
            "stn_separator": stn_separator,
            "stn_ignore_repeats": stn_ignore_repeats,
            "stn_join_attention": stn_join_attention,
            "cleanup_extra_spaces": cleanup_extra_spaces,
            "cleanup_empty_constructs": cleanup_empty_constructs,
            "cleanup_extra_separators": cleanup_extra_separators,
            "cleanup_extra_separators2": cleanup_extra_separators2,
            "cleanup_breaks": cleanup_breaks,
            "cleanup_breaks_eol": cleanup_breaks_eol,
            "cleanup_ands": cleanup_ands,
            "cleanup_ands_eol": cleanup_ands_eol,
            "cleanup_extranetwork_tags": cleanup_extranetwork_tags,
            "remove_extranetwork_tags": remove_extranetwork_tags,
        }
        return new_run.__hash__
        # return float("NaN")

    def process(
        self,
        model,
        modelname,
        pos_prompt,
        neg_prompt,
        seed,
        debug_level,
        pony_substrings,
        wc_process_wildcards,
        wc_wildcards_folders,
        wc_if_wildcards,
        wc_choice_separator,
        wc_keep_choices_order,
        stn_separator,
        stn_ignore_repeats,
        stn_join_attention,
        cleanup_extra_spaces,
        cleanup_empty_constructs,
        cleanup_extra_separators,
        cleanup_extra_separators2,
        cleanup_breaks,
        cleanup_breaks_eol,
        cleanup_ands,
        cleanup_ands_eol,
        cleanup_extranetwork_tags,
        remove_extranetwork_tags,
    ):
        model_info = {
            "models_path": folder_paths.models_dir,
            "model_filename": modelname, # path is relative to checkpoints folder
            "is_sd1": model.model.model_config.__class__.__name__ in ("SD15", "SD15_instructpix2pix"),
            "is_sd2": model.model.model_config.__class__.__name__ in ("SD20", "SD21UnclipL", "SD21UnclipH"),
            "is_sdxl": model.model.model_config.__class__.__name__
            in (
                "SDXL",
                "SDXLRefiner",
                "SDXL_instructpix2pix",
                "Segmind_Vega",
                "KOALA_700M",
                "KOALA_1B",
            ),
            "is_ssd": model.model.model_config.__class__.__name__ in ("SSD1B"),
            "is_sd3": model.model.model_config.__class__.__name__ in ("SD3"),
            "is_flux": model.model.model_config.__class__.__name__ in ("Flux"),
        }
        # SVD_img2vid, SVD3D_u, SVD3_p, Stable_Zero123, SD_X4Upscaler,
        # Stable_Cascade_C, Stable_Cascade_B, StableAudio

        if wc_wildcards_folders == "":
            wc_wildcards_folders = ",".join(folder_paths.get_folder_paths("wildcards") or [])
        if wc_wildcards_folders == "":
            wc_wildcards_folders = os.getenv("WILDCARD_DIR", PPPWildcards.DEFAULT_WILDCARDS_FOLDER)
        wildcards_folders = [
            (f if os.path.isabs(f) else os.path.abspath(os.path.join(folder_paths.models_dir, f)))
            for f in wc_wildcards_folders.split(",")
            if f.strip() != ""
        ]
        options = {
            "debug_level": debug_level,
            "pony_substrings": pony_substrings,
            "process_wildcards": wc_process_wildcards,
            "if_wildcards": wc_if_wildcards,
            "choice_separator": wc_choice_separator,
            "keep_choices_order": wc_keep_choices_order,
            "stn_separator": stn_separator,
            "stn_ignore_repeats": stn_ignore_repeats,
            "stn_join_attention": stn_join_attention,
            "cleanup_extra_spaces": cleanup_extra_spaces,
            "cleanup_empty_constructs": cleanup_empty_constructs,
            "cleanup_extra_separators": cleanup_extra_separators,
            "cleanup_extra_separators2": cleanup_extra_separators2,
            "cleanup_breaks": cleanup_breaks,
            "cleanup_breaks_eol": cleanup_breaks_eol,
            "cleanup_ands": cleanup_ands,
            "cleanup_ands_eol": cleanup_ands_eol,
            "cleanup_extranetwork_tags": cleanup_extranetwork_tags,
            "remove_extranetwork_tags": remove_extranetwork_tags,
        }
        self.wildcards_obj.refresh_wildcards(debug_level, wildcards_folders if options["process_wildcards"] else None)
        ppp = PromptPostProcessor(
            self.logger, self.interrupt, model_info, options, self.grammar_content, self.wildcards_obj
        )
        pos_prompt, neg_prompt = ppp.process_prompt(pos_prompt, neg_prompt, seed if seed is not None else 1)
        return (
            pos_prompt,
            neg_prompt,
        )

    def interrupt(self):
        nodes.interrupt_processing(True)
