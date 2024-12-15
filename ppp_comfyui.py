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

    logger = None

    def __init__(self):
        lf = PromptPostProcessorLogFactory()
        self.logger = lf.log
        grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "grammar.lark")
        with open(grammar_filename, "r", encoding="utf-8") as file:
            self.grammar_content = file.read()
        self.wildcards_obj = PPPWildcards(lf.log)
        self.logger.info(f"{PromptPostProcessor.NAME} {PromptPostProcessor.VERSION} initialized")

    class SmartType(str):
        def __ne__(self, other):
            if self == "*" or other == "*":
                return False
            selfset = set(self.split(","))
            otherset = set(other.split(","))
            return not otherset.issubset(selfset)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pos_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "dynamicPrompts": False,
                        "defaultInput": True,
                        "forceInput": False,
                    },
                ),
                "neg_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "dynamicPrompts": False,
                        "defaultInput": True,
                        "forceInput": False,
                    },
                ),
            },
            "optional": {
                "model": (
                    cls.SmartType("MODEL,STRING"),
                    {
                        "default": "",
                        "placeholder": "internal model class name",
                        "forceInput": True,
                    },
                ),
                "modelname": (
                    "STRING",
                    {
                        "default": "",
                        "placeholder": "full path of the model",
                        "defaultInput": True,
                        "forceInput": False,
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": -1,
                        "defaultInput": True,
                        "forceInput": False,
                    },
                ),
                "debug_level": (
                    [e.value for e in DEBUG_LEVEL],
                    {
                        "default": DEBUG_LEVEL.minimal.value,
                        "tooltip": "Debug level",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "variants_definitions": (
                    "STRING",
                    {
                        "default": PromptPostProcessor.DEFAULT_VARIANTS_DEFINITIONS,
                        "multiline": True,
                        "placeholder": "",
                        "tooltip": "Definitions for variant models to be recognized based on strings found in the full filename. Format for each line is: 'name(kind)=comma separated list of substrings (case insensitive)' with kind being one of the base model types or not specified",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "wc_process_wildcards": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Process wildcards in the prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "wc_wildcards_folders": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Comma separated list of wildcards folders",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "wc_if_wildcards": (
                    [e.value for e in PromptPostProcessor.IFWILDCARDS_CHOICES],
                    {
                        "default": PromptPostProcessor.IFWILDCARDS_CHOICES.ignore.value,
                        "tooltip": "How to handle invalid wildcards in the prompt",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "wc_choice_separator": (
                    "STRING",
                    {
                        "default": PromptPostProcessor.DEFAULT_CHOICE_SEPARATOR,
                        "tooltip": "Default separator for selected choices",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "wc_keep_choices_order": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Keep the order of the choices in the prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "stn_separator": (
                    "STRING",
                    {
                        "default": PromptPostProcessor.DEFAULT_STN_SEPARATOR,
                        "tooltip": "Separator for the content added to the negative prompt",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "stn_ignore_repeats": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Ignore repeated content added to the negative prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "cleanup_extra_spaces": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove extra spaces",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "cleanup_empty_constructs": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove empty constructs",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "cleanup_extra_separators": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove extra separators",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "cleanup_extra_separators2": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Remove extra separators (additional cases)",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "cleanup_breaks": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Cleanup around BREAKs",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "cleanup_breaks_eol": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Set BREAKs in their own line",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "cleanup_ands": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Cleanup around ANDs",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "cleanup_ands_eol": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Set ANDs in their own line",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "cleanup_extranetwork_tags": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Clean up around extra network tags",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "cleanup_merge_attention": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Merge nested attention constructs",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
                "remove_extranetwork_tags": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Remove extra network tags",
                        "label_on": "Yes",
                        "label_off": "No",
                        "defaultInput": False,
                        "forceInput": False,
                    },
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, input_types: dict[str, str]):
        it = cls.INPUT_TYPES()
        expected = {
            k: cls.SmartType("COMBO,STRING") if isinstance(v[0], list) else v[0]  # we allow string for combos
            for k, v in {**it["required"], **it["optional"]}.items()
        }
        for input_name, input_type in input_types.items():
            t = expected[input_name]
            if input_type != t:
                return f"Invalid type for input '{input_name}': {input_type} (expected {t})"
        return True

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
        variants_definitions,
        wc_process_wildcards,
        wc_wildcards_folders,
        wc_if_wildcards,
        wc_choice_separator,
        wc_keep_choices_order,
        stn_separator,
        stn_ignore_repeats,
        cleanup_extra_spaces,
        cleanup_empty_constructs,
        cleanup_extra_separators,
        cleanup_extra_separators2,
        cleanup_breaks,
        cleanup_breaks_eol,
        cleanup_ands,
        cleanup_ands_eol,
        cleanup_extranetwork_tags,
        cleanup_merge_attention,
        remove_extranetwork_tags,
    ):
        if wc_process_wildcards:
            return float("NaN") # since we can't detect changes in wildcards we assume they are always changed when enabled
        new_run = {  # everything except debug_level
            "model": model,
            "modelname": modelname,
            "pos_prompt": pos_prompt,
            "neg_prompt": neg_prompt,
            "seed": seed,
            "variants_definitions": variants_definitions,
            "process_wildcards": wc_process_wildcards,
            "wildcards_folders": wc_wildcards_folders,
            "if_wildcards": wc_if_wildcards,
            "choice_separator": wc_choice_separator,
            "keep_choices_order": wc_keep_choices_order,
            "stn_separator": stn_separator,
            "stn_ignore_repeats": stn_ignore_repeats,
            "cleanup_extra_spaces": cleanup_extra_spaces,
            "cleanup_empty_constructs": cleanup_empty_constructs,
            "cleanup_extra_separators": cleanup_extra_separators,
            "cleanup_extra_separators2": cleanup_extra_separators2,
            "cleanup_breaks": cleanup_breaks,
            "cleanup_breaks_eol": cleanup_breaks_eol,
            "cleanup_ands": cleanup_ands,
            "cleanup_ands_eol": cleanup_ands_eol,
            "cleanup_extranetwork_tags": cleanup_extranetwork_tags,
            "cleanup_merge_attention": cleanup_merge_attention,
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
        variants_definitions,
        wc_process_wildcards,
        wc_wildcards_folders,
        wc_if_wildcards,
        wc_choice_separator,
        wc_keep_choices_order,
        stn_separator,
        stn_ignore_repeats,
        cleanup_extra_spaces,
        cleanup_empty_constructs,
        cleanup_extra_separators,
        cleanup_extra_separators2,
        cleanup_breaks,
        cleanup_breaks_eol,
        cleanup_ands,
        cleanup_ands_eol,
        cleanup_extranetwork_tags,
        cleanup_merge_attention,
        remove_extranetwork_tags,
    ):
        modelclass = (
            model.model.model_config.__class__.__name__ if model is not None and not isinstance(model, str) else model
        ) or ""
        if modelclass == "":
            self.logger.warning("Model class is not provided. System variables might not be properly set.")
        if modelname == "":
            self.logger.warning("Modelname is not provided. System variables will not be properly set.")
        env_info = {
            "app": "comfyui",
            "models_path": folder_paths.models_dir,
            "model_filename": modelname or "",  # path is relative to checkpoints folder
            "model_class": modelclass,
            "is_sd1": modelclass in ("SD15", "SD15_instructpix2pix"),
            "is_sd2": modelclass in ("SD20", "SD21UnclipL", "SD21UnclipH"),
            "is_sdxl": (
                modelclass in ("SDXL", "SDXLRefiner", "SDXL_instructpix2pix", "Segmind_Vega", "KOALA_700M", "KOALA_1B")
            ),
            "is_ssd": modelclass in ("SSD1B",),
            "is_sd3": modelclass in ("SD3",),
            "is_flux": modelclass in ("Flux",),
            "is_auraflow": modelclass in ("AuraFlow",),
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
            "variants_definitions": variants_definitions,
            "process_wildcards": wc_process_wildcards,
            "if_wildcards": wc_if_wildcards,
            "choice_separator": wc_choice_separator,
            "keep_choices_order": wc_keep_choices_order,
            "stn_separator": stn_separator,
            "stn_ignore_repeats": stn_ignore_repeats,
            "cleanup_extra_spaces": cleanup_extra_spaces,
            "cleanup_empty_constructs": cleanup_empty_constructs,
            "cleanup_extra_separators": cleanup_extra_separators,
            "cleanup_extra_separators2": cleanup_extra_separators2,
            "cleanup_breaks": cleanup_breaks,
            "cleanup_breaks_eol": cleanup_breaks_eol,
            "cleanup_ands": cleanup_ands,
            "cleanup_ands_eol": cleanup_ands_eol,
            "cleanup_extranetwork_tags": cleanup_extranetwork_tags,
            "cleanup_merge_attention": cleanup_merge_attention,
            "remove_extranetwork_tags": remove_extranetwork_tags,
        }
        self.wildcards_obj.refresh_wildcards(debug_level, wildcards_folders if options["process_wildcards"] else None)
        ppp = PromptPostProcessor(
            self.logger, self.interrupt, env_info, options, self.grammar_content, self.wildcards_obj
        )
        pos_prompt, neg_prompt = ppp.process_prompt(pos_prompt, neg_prompt, seed if seed is not None else 1)
        return (
            pos_prompt,
            neg_prompt,
        )

    def interrupt(self):
        nodes.interrupt_processing(True)
