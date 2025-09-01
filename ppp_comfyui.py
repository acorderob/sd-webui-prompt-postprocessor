import os

# pylint: disable=import-error
import folder_paths  # type: ignore
import nodes

from .ppp import PromptPostProcessor
from .ppp_hosts import SUPPORTED_APPS
from .ppp_logging import DEBUG_LEVEL, PromptPostProcessorLogFactory
from .ppp_wildcards import PPPWildcards
from .ppp_enmappings import PPPExtraNetworkMappings

if __name__ == "__main__":
    raise SystemExit("This script must be run from ComfyUI")


class PromptPostProcessorComfyUINode:
    """
    Node for processing prompts.
    """

    logger = None

    def __init__(self):
        lf = PromptPostProcessorLogFactory(SUPPORTED_APPS.comfyui)
        self.logger = lf.log
        grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "grammar.lark")
        with open(grammar_filename, "r", encoding="utf-8") as file:
            self.grammar_content = file.read()
        self.wildcards_obj = PPPWildcards(lf.log)
        self.extranetwork_mappings_obj = PPPExtraNetworkMappings(lf.log)
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
                    },
                ),
                "neg_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "dynamicPrompts": False,
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
                        "dynamicPrompts": False,
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": -1,
                    },
                ),
                "debug_level": (
                    [e.value for e in DEBUG_LEVEL],
                    {
                        "default": DEBUG_LEVEL.minimal.value,
                        "tooltip": "Debug level",
                    },
                ),
                "on_warnings": (
                    [e.value for e in PromptPostProcessor.ONWARNING_CHOICES],
                    {
                        "default": PromptPostProcessor.ONWARNING_CHOICES.warn.value,
                        "tooltip": "How to handle invalid content warnings",
                    },
                ),
                "variants_definitions": (
                    "STRING",
                    {
                        "default": PromptPostProcessor.DEFAULT_VARIANTS_DEFINITIONS,
                        "multiline": True,
                        "placeholder": "",
                        "tooltip": "Definitions for variant models to be recognized based on strings found in the full filename. Format for each line is: 'name(kind)=comma separated list of substrings (case insensitive)' with kind being one of the base model types or not specified",
                        "dynamicPrompts": False,
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
                        "dynamicPrompts": False,
                    },
                ),
                "wc_wildcards_input": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "wildcards definitions",
                        "tooltip": "Wildcards definitions in yaml/json format",
                        "dynamicPrompts": False,
                    },
                ),
                "wc_if_wildcards": (
                    [e.value for e in PromptPostProcessor.IFWILDCARDS_CHOICES],
                    {
                        "default": PromptPostProcessor.IFWILDCARDS_CHOICES.stop.value,
                        "tooltip": "How to handle invalid wildcards in the prompt",
                    },
                ),
                "wc_choice_separator": (
                    "STRING",
                    {
                        "default": PromptPostProcessor.DEFAULT_CHOICE_SEPARATOR,
                        "tooltip": "Default separator for selected choices",
                        "dynamicPrompts": False,
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
                        "dynamicPrompts": False,
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
                "cleanup_extra_separators_include_eol": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Extra separators options also remove EOLs",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_breaks": (
                    "BOOLEAN",
                    {
                        "default": False,
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
                        "default": False,
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
                "cleanup_merge_attention": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": "Merge nested attention constructs",
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
                "en_mappings_folders": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Comma separated list of extranetwork mappings folders",
                        "dynamicPrompts": False,
                    },
                ),
                "en_mappings_input": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "extranetwork mappings definitions",
                        "tooltip": "Extranetwork mappings definitions in yaml format",
                        "dynamicPrompts": False,
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
        "PPP_DICT",
    )
    RETURN_NAMES = (
        "pos_prompt",
        "neg_prompt",
        "variables",
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
        on_warnings,
        variants_definitions,
        wc_process_wildcards,
        wc_wildcards_folders,
        wc_wildcards_input,
        wc_if_wildcards,
        wc_choice_separator,
        wc_keep_choices_order,
        stn_separator,
        stn_ignore_repeats,
        cleanup_extra_spaces,
        cleanup_empty_constructs,
        cleanup_extra_separators,
        cleanup_extra_separators2,
        cleanup_extra_separators_include_eol,
        cleanup_breaks,
        cleanup_breaks_eol,
        cleanup_ands,
        cleanup_ands_eol,
        cleanup_extranetwork_tags,
        cleanup_merge_attention,
        remove_extranetwork_tags,
        en_mappings_folders,
        en_mappings_input,
    ):
        if wc_process_wildcards:
            return float(
                "NaN"
            )  # since we can't detect changes in wildcards we assume they are always changed when enabled
        new_run = {  # everything except debug_level
            "model": model,
            "modelname": modelname,
            "pos_prompt": pos_prompt,
            "neg_prompt": neg_prompt,
            "seed": seed,
            "on_warnings": on_warnings,
            "variants_definitions": variants_definitions,
            "process_wildcards": wc_process_wildcards,
            "wildcards_folders": wc_wildcards_folders,
            "wildcards_input": wc_wildcards_input,
            "if_wildcards": wc_if_wildcards,
            "choice_separator": wc_choice_separator,
            "keep_choices_order": wc_keep_choices_order,
            "stn_separator": stn_separator,
            "stn_ignore_repeats": stn_ignore_repeats,
            "cleanup_extra_spaces": cleanup_extra_spaces,
            "cleanup_empty_constructs": cleanup_empty_constructs,
            "cleanup_extra_separators": cleanup_extra_separators,
            "cleanup_extra_separators2": cleanup_extra_separators2,
            "cleanup_extra_separators_include_eol": cleanup_extra_separators_include_eol,
            "cleanup_breaks": cleanup_breaks,
            "cleanup_breaks_eol": cleanup_breaks_eol,
            "cleanup_ands": cleanup_ands,
            "cleanup_ands_eol": cleanup_ands_eol,
            "cleanup_extranetwork_tags": cleanup_extranetwork_tags,
            "cleanup_merge_attention": cleanup_merge_attention,
            "remove_extranetwork_tags": remove_extranetwork_tags,
            "en_mappings_folders": en_mappings_folders,
            "en_mappings_input": en_mappings_input,
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
        on_warnings,
        variants_definitions,
        wc_process_wildcards,
        wc_wildcards_folders,
        wc_wildcards_input,
        wc_if_wildcards,
        wc_choice_separator,
        wc_keep_choices_order,
        stn_separator,
        stn_ignore_repeats,
        cleanup_extra_spaces,
        cleanup_empty_constructs,
        cleanup_extra_separators,
        cleanup_extra_separators2,
        cleanup_extra_separators_include_eol,
        cleanup_breaks,
        cleanup_breaks_eol,
        cleanup_ands,
        cleanup_ands_eol,
        cleanup_extranetwork_tags,
        cleanup_merge_attention,
        remove_extranetwork_tags,
        en_mappings_folders,
        en_mappings_input,
    ):
        modelclass = (
            model.model.model_config.__class__.__name__ if model is not None and not isinstance(model, str) else model
        ) or ""
        if modelclass == "":
            self.logger.warning("Model class is not provided. System variables might not be properly set.")
        if modelname == "":
            self.logger.warning("Modelname is not provided. System variables will not be properly set.")
        # model class values in ComfyUI\comfy\supported_models.py
        env_info = {
            "app": SUPPORTED_APPS.comfyui.value,
            "models_path": folder_paths.models_dir,
            "model_filename": modelname or "",  # path is relative to checkpoints folder
            "model_class": modelclass,
            "is_sd1": modelclass in ("SD15", "SD15_instructpix2pix"),
            "is_sd2": modelclass in ("SD20", "SD21UnclipL", "SD21UnclipH", "LotusD"),
            "is_sdxl": (
                modelclass in ("SDXL", "SDXLRefiner", "SDXL_instructpix2pix", "Segmind_Vega", "KOALA_700M", "KOALA_1B")
            ),
            "is_ssd": modelclass in ("SSD1B",),
            "is_sd3": modelclass in ("SD3",),
            "is_flux": modelclass in ("Flux", "FluxInpaint", "FluxSchnell"),
            "is_auraflow": modelclass in ("AuraFlow",),
            "is_pixart": modelclass in ("PixArtAlpha", "PixArtSigma"),
            "is_lumina2": modelclass in ("Lumina2",),
            "is_ltxv": modelclass in ("LTXV",),
            "is_cosmos": modelclass in ("CosmosT2V", "CosmosI2V"),
            "is_genmomochi": modelclass in ("GenmoMochi",),
            "is_hunyuan": modelclass in ("HunyuanDiT", "HunyuanDiT1"),
            "is_hunyuanvideo": modelclass in ("HunyuanVideo", "HunyuanVideoI2V", "HunyuanVideoSkyreelsI2V"),
            "is_hunyuan3d": modelclass in ("Hunyuan3Dv2", "Hunyuan3Dv2mini"),
            "is_wanvideo": modelclass in ("WAN21_T2V", "WAN21_I2V", "WAN21_FunControl2V"),
            "is_hidream": modelclass in ("HiDream",),
        }
        # Also supported: SVD_img2vid, SVD3D_u, SVD3_p, Stable_Zero123, SD_X4Upscaler, Stable_Cascade_C, Stable_Cascade_B, StableAudio

        if wc_wildcards_folders == "":
            try:
                fp1 = folder_paths.get_folder_paths("ppp_wildcards")
            except Exception:  # pylint: disable=W0718
                fp1 = None
            try:
                fp2 = folder_paths.get_folder_paths("wildcards")
            except Exception:  # pylint: disable=W0718
                fp2 = None
            wc_wildcards_folders = ",".join(fp1 or fp2 or [])
        if wc_wildcards_folders == "":
            wc_wildcards_folders = os.getenv("WILDCARD_DIR", PPPWildcards.DEFAULT_WILDCARDS_FOLDER)
        wildcards_folders = [
            (f if os.path.isabs(f) else os.path.abspath(os.path.join(folder_paths.models_dir, f)))
            for f in wc_wildcards_folders.split(",")
            if f.strip() != ""
        ]
        if en_mappings_folders == "":
            try:
                fp3 = folder_paths.get_folder_paths("ppp_extranetworkmappings")
            except Exception:  # pylint: disable=W0718
                fp3 = None
            en_mappings_folders = ",".join(fp3 or [])
        if en_mappings_folders == "":
            en_mappings_folders = os.getenv(
                "EXTRANETWORKMAPPINGS_DIR", PPPExtraNetworkMappings.DEFAULT_ENMAPPINGS_FOLDER
            )
        enmappings_folders = [
            (f if os.path.isabs(f) else os.path.abspath(os.path.join(folder_paths.models_dir, f)))
            for f in en_mappings_folders.split(",")
            if f.strip() != ""
        ]

        if variants_definitions != "" and not "=" in variants_definitions:  # mainly to warn about the old format
            raise ValueError("Invalid variants_definitions format")
        options = {
            "debug_level": debug_level,
            "on_warnings": on_warnings,
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
            "cleanup_extra_separators_include_eol": cleanup_extra_separators_include_eol,
            "cleanup_breaks": cleanup_breaks,
            "cleanup_breaks_eol": cleanup_breaks_eol,
            "cleanup_ands": cleanup_ands,
            "cleanup_ands_eol": cleanup_ands_eol,
            "cleanup_extranetwork_tags": cleanup_extranetwork_tags,
            "cleanup_merge_attention": cleanup_merge_attention,
            "remove_extranetwork_tags": remove_extranetwork_tags,
        }
        self.wildcards_obj.refresh_wildcards(
            debug_level,
            wildcards_folders if options["process_wildcards"] else None,
            wc_wildcards_input,
        )
        self.extranetwork_mappings_obj.refresh_extranetwork_mappings(
            debug_level,
            enmappings_folders,
            en_mappings_input,
        )
        ppp = PromptPostProcessor(
            self.logger,
            self.interrupt,
            env_info,
            options,
            self.grammar_content,
            self.wildcards_obj,
            self.extranetwork_mappings_obj,
        )
        pos_prompt, neg_prompt, variables = ppp.process_prompt(pos_prompt, neg_prompt, seed if seed is not None else 1)
        return (
            pos_prompt,
            neg_prompt,
            variables,
        )

    def interrupt(self):
        nodes.interrupt_processing(True)


class PromptPostProcessorSelectVariableComfyUINode:
    """
    Node for selecting a variable from a dictionary.
    """

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "variables": (
                    "PPP_DICT",
                    {
                        "forceInput": True,
                    },
                ),
            },
            "optional": {
                "name": (
                    "STRING",
                    {
                        "placeholder": "variable name",
                        "multiline": False,
                        "default": "",
                        "dynamicPrompts": False,
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("value",)

    FUNCTION = "select"

    CATEGORY = "ACB"

    def select(
        self,
        variables: dict[str, str],
        name: str,
    ):
        value = ""
        if variables:
            if name == "":
                value = "\n".join(f"{k}: {v}" for k, v in variables.items())
            elif name in variables:
                value = variables[name]
        return (value,)
