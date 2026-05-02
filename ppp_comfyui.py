import logging
import os

import folder_paths  # type: ignore
import nodes  # type: ignore

from ppp import PromptPostProcessor
from ppp_classes import IFWILDCARDS_CHOICES, ONWARNING_CHOICES, SUPPORTED_APPS, PPPStateOptions
from ppp_logging import DEBUG_LEVEL, PromptPostProcessorLogFactory, log
from ppp_utils import escape_single_quotes
from ppp_wildcards import PPPWildcards
from ppp_enmappings import PPPExtraNetworkMappings

if __name__ == "__main__":
    raise SystemExit("This script must be run from ComfyUI")


def _resolve_wildcards_folders(override: str = "") -> list[str]:
    """Return the resolved list of wildcard folder paths."""
    folders_str = override
    if folders_str == "":
        try:
            fp1 = folder_paths.get_folder_paths("ppp_wildcards")
        except Exception:  # pylint: disable=W0718
            fp1 = None
        try:
            fp2 = folder_paths.get_folder_paths("wildcards")
        except Exception:  # pylint: disable=W0718
            fp2 = None
        folders_str = ",".join(fp1 or fp2 or [])
    if folders_str == "":
        folders_str = os.getenv("WILDCARD_DIR", PPPWildcards.DEFAULT_WILDCARDS_FOLDER)
    return [
        (f if os.path.isabs(f) else os.path.abspath(os.path.join(folder_paths.models_dir, f)))
        for f in folders_str.split(",")
        if f.strip() != ""
    ]


def _resolve_enmappings_folders(override: str = "") -> list[str]:
    """Return the resolved list of extra-network mapping folder paths."""
    folders_str = override
    if folders_str == "":
        try:
            fp3 = folder_paths.get_folder_paths("ppp_extranetworkmappings")
        except Exception:  # pylint: disable=W0718
            fp3 = None
        folders_str = ",".join(fp3 or [])
    if folders_str == "":
        folders_str = os.getenv("EXTRANETWORKMAPPINGS_DIR", PPPExtraNetworkMappings.DEFAULT_ENMAPPINGS_FOLDER)
    return [
        (f if os.path.isabs(f) else os.path.abspath(os.path.join(folder_paths.models_dir, f)))
        for f in folders_str.split(",")
        if f.strip() != ""
    ]


class PromptPostProcessorComfyUINode:
    """
    Node for processing prompts.
    """

    logger = None

    def __init__(self):
        lf = PromptPostProcessorLogFactory()
        self.logger = lf.log
        grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "grammar.lark")
        with open(grammar_filename, "r", encoding="utf-8") as file:
            self.grammar_content = file.read()
        self.wildcards_obj = PPPWildcards(lf.log)
        self.extranetwork_mappings_obj = PPPExtraNetworkMappings(lf.log)
        log(
            self.logger,
            DEBUG_LEVEL.minimal,
            logging.INFO,
            f"{PromptPostProcessor.NAME} {PromptPostProcessor.VERSION} initialized",
        )

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
                        "min": -1,
                        "tooltip": "Seed value for the prompt processing (use -1 for random)",
                    },
                ),
                "debug_level": (
                    [e.value for e in DEBUG_LEVEL],
                    {
                        "default": PromptPostProcessor.DEFAULT_DEBUG_LEVEL,
                        "tooltip": "Debug level",
                    },
                ),
                "on_warnings": (
                    [e.value for e in ONWARNING_CHOICES],
                    {
                        "default": PromptPostProcessor.DEFAULT_ON_WARNING,
                        "tooltip": "How to handle invalid content warnings",
                    },
                ),
                "strict_operators": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_STRICT_OPERATORS,
                        "tooltip": "Use strict operators",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "process_wildcards": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_PROCESS_WILDCARDS,
                        "tooltip": "Process wildcards in the prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "do_cleanup": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_DO_CLEANUP,
                        "tooltip": "Do a cleanup of the prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "cleanup_variables": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CLEANUP_VARIABLES,
                        "tooltip": "Do a cleanup of the output variables",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "do_combinatorial": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_DO_COMBINATORIAL,
                        "tooltip": "Enable combinatorial mode",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "combinatorial_shuffle": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_COMBINATORIAL_SHUFFLE,
                        "tooltip": "Shuffle the combinatorial results",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "combinatorial_limit": (
                    "INT",
                    {
                        "default": PromptPostProcessor.DEFAULT_COMBINATORIAL_LIMIT,
                        "tooltip": "Limit for combinatorial mode",
                    },
                ),
                "wc_options": (
                    "PPP_OPTIONS_WC",
                    {
                        "default": None,
                        "tooltip": "Wildcard processing options",
                    },
                ),
                "stn_options": (
                    "PPP_OPTIONS_STN",
                    {
                        "default": None,
                        "tooltip": "Send-To-Negative options",
                    },
                ),
                "cup_options": (
                    "PPP_OPTIONS_CUP",
                    {
                        "default": None,
                        "tooltip": "Cleanup options",
                    },
                ),
                "en_options": (
                    "PPP_OPTIONS_EN",
                    {
                        "default": None,
                        "tooltip": "ExtraNetworks mapping options",
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
                return f"Invalid type for input '{escape_single_quotes(input_name)}': {input_type} (expected {t})"
        return True

    RETURN_TYPES = (
        "STRING",
        "STRING",
        "PPP_DICT",
    )
    OUTPUT_IS_LIST = (
        True,
        True,
        True,
    )
    RETURN_NAMES = (
        "pos_prompt",
        "neg_prompt",
        "variables",
    )

    FUNCTION = "process"

    CATEGORY = "ACB"

    @classmethod
    def IS_CHANGED(cls, **kwargs):  # pylint: disable=unused-argument
        return float("NaN")  # always process because we don't control the content of wildcards and the config file

    def process(
        self,
        model,
        modelname,
        pos_prompt,
        neg_prompt,
        seed,
        debug_level,
        on_warnings,
        process_wildcards,
        do_cleanup,
        cleanup_variables,
        do_combinatorial,
        combinatorial_shuffle,
        combinatorial_limit,
        wc_options=None,
        stn_options=None,
        cup_options=None,
        en_options=None,
        strict_operators=None,
    ):
        modelclass = (
            model.model.model_config.__class__.__name__ if model is not None and not isinstance(model, str) else model
        ) or ""
        if modelclass == "":
            log(
                self.logger,
                DEBUG_LEVEL.minimal,
                logging.WARNING,
                "Model class is not provided. System variables might not be properly set.",
            )
        if modelname == "":
            log(
                self.logger,
                DEBUG_LEVEL.minimal,
                logging.WARNING,
                "Modelname is not provided. System variables will not be properly set.",
            )
        # model class values in ComfyUI\comfy\supported_models.py
        env_info = {
            "app": SUPPORTED_APPS.comfyui.value,
            "models_path": folder_paths.models_dir,
            "model_filename": modelname or "",  # path is relative to checkpoints folder
            "model_class": modelclass,
            "property_base": None,
        }
        wildcards_folders = _resolve_wildcards_folders(wc_options["wc_wildcards_folders"] if wc_options else "")
        enmappings_folders = _resolve_enmappings_folders(en_options["en_mappings_folders"] if en_options else "")

        options = PPPStateOptions(
            debug_level=DEBUG_LEVEL(debug_level),
            on_warning=ONWARNING_CHOICES(on_warnings) if on_warnings else PromptPostProcessor.DEFAULT_ON_WARNING,
            strict_operators=(
                strict_operators if strict_operators is not None else PromptPostProcessor.DEFAULT_STRICT_OPERATORS
            ),
            process_wildcards=process_wildcards,
            if_wildcards=(wc_options["wc_if_wildcards"] if wc_options else IFWILDCARDS_CHOICES.stop.value),
            choice_separator=(
                wc_options["wc_choice_separator"] if wc_options else PromptPostProcessor.DEFAULT_CHOICE_SEPARATOR
            ),
            keep_choices_order=(
                wc_options["wc_keep_choices_order"] if wc_options else PromptPostProcessor.DEFAULT_KEEP_CHOICES_ORDER
            ),
            stn_separator=stn_options["stn_separator"] if stn_options else PromptPostProcessor.DEFAULT_STN_SEPARATOR,
            stn_ignore_repeats=(
                stn_options["stn_ignore_repeats"] if stn_options else PromptPostProcessor.DEFAULT_STN_IGNORE_REPEATS
            ),
            cup_do_cleanup=do_cleanup,
            cup_cleanup_variables=cleanup_variables,
            cup_extra_spaces=(
                cup_options["cup_extra_spaces"] if cup_options else PromptPostProcessor.DEFAULT_CUP_EXTRA_SPACES
            ),
            cup_empty_constructs=(
                cup_options["cup_empty_constructs"] if cup_options else PromptPostProcessor.DEFAULT_CUP_EMPTY_CONSTRUCTS
            ),
            cup_extra_separators=(
                cup_options["cup_extra_separators"] if cup_options else PromptPostProcessor.DEFAULT_CUP_EXTRA_SEPARATORS
            ),
            cup_extra_separators2=(
                cup_options["cup_extra_separators2"]
                if cup_options
                else PromptPostProcessor.DEFAULT_CUP_EXTRA_SEPARATORS2
            ),
            cup_extra_separators_include_eol=(
                cup_options["cup_extra_separators_include_eol"]
                if cup_options
                else PromptPostProcessor.DEFAULT_CUP_EXTRA_SEPARATORS_INCLUDE_EOL
            ),
            cup_breaks=cup_options["cup_breaks"] if cup_options else PromptPostProcessor.DEFAULT_CUP_BREAKS,
            cup_breaks_eol=(
                cup_options["cup_breaks_eol"] if cup_options else PromptPostProcessor.DEFAULT_CUP_BREAKS_EOL
            ),
            cup_ands=cup_options["cup_ands"] if cup_options else PromptPostProcessor.DEFAULT_CUP_ANDS,
            cup_ands_eol=(cup_options["cup_ands_eol"] if cup_options else PromptPostProcessor.DEFAULT_CUP_ANDS_EOL),
            cup_extranetwork_tags=(
                cup_options["cup_extranetwork_tags"]
                if cup_options
                else PromptPostProcessor.DEFAULT_CUP_EXTRANETWORK_TAGS
            ),
            cup_merge_attention=(
                cup_options["cup_merge_attention"] if cup_options else PromptPostProcessor.DEFAULT_CUP_MERGE_ATTENTION
            ),
            cup_remove_extranetwork_tags=(
                cup_options["cup_remove_extranetwork_tags"]
                if cup_options
                else PromptPostProcessor.DEFAULT_CUP_REMOVE_EXTRANETWORK_TAGS
            ),
            do_combinatorial=do_combinatorial,
            combinatorial_shuffle=combinatorial_shuffle,
            combinatorial_limit=combinatorial_limit,
        )
        self.wildcards_obj.refresh_wildcards(
            options.debug_level,
            wildcards_folders if options.process_wildcards else None,
            wc_options["wc_wildcards_input"] if wc_options else "",
        )
        self.extranetwork_mappings_obj.refresh_extranetwork_mappings(
            options.debug_level,
            enmappings_folders,
            en_options["en_mappings_input"] if en_options else "",
        )
        ppp = PromptPostProcessor(
            self.logger,
            env_info,
            options,
            self.grammar_content,
            self.interrupt,
            self.wildcards_obj,
            self.extranetwork_mappings_obj,
        )
        results = ppp.process_prompt(pos_prompt, neg_prompt, seed if seed is not None else 1)

        # with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "logs", "last_prompts_comfyui.txt"), "w", encoding="utf-8") as f:
        #     f.write(f"Seed: {seed if seed is not None else 1}\n")
        #     f.write(f"In Positive: {pos_prompt}\n")
        #     f.write(f"In Negative: {neg_prompt}\n")
        #     f.write("\n")
        #     for i, (posp, negp, var) in enumerate(results):
        #         f.write(f"Index: {i}\n")
        #         f.write(f"Out Positive: {posp}\n")
        #         f.write(f"Out Negative: {negp}\n")
        #         f.write(f"Out Variables: {var}\n")
        #         f.write("\n")

        return tuple(zip(*results))  # unzip the list of tuples into tuple of lists

    def interrupt(self):
        nodes.interrupt_processing(True)


class PromptPostProcessorWildcardOptionsComfyUINode:
    """
    Node for wildcard options.
    """

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "folders": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Comma separated list of wildcards folders",
                        "dynamicPrompts": False,
                    },
                ),
                "definitions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "wildcards definitions",
                        "tooltip": "Wildcards definitions in yaml/json format",
                        "dynamicPrompts": False,
                    },
                ),
                "if_wildcards": (
                    [e.value for e in IFWILDCARDS_CHOICES],
                    {
                        "default": IFWILDCARDS_CHOICES.stop.value,
                        "tooltip": "How to handle invalid wildcards in the prompt",
                    },
                ),
                "choice_separator": (
                    "STRING",
                    {
                        "default": PromptPostProcessor.DEFAULT_CHOICE_SEPARATOR,
                        "tooltip": "Default separator for selected choices",
                        "dynamicPrompts": False,
                    },
                ),
                "keep_choices_order": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_KEEP_CHOICES_ORDER,
                        "tooltip": "Keep the order of the choices in the prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
            },
        }

    RETURN_TYPES = ("PPP_OPTIONS_WC",)
    RETURN_NAMES = ("options",)

    FUNCTION = "process"

    CATEGORY = "ACB"

    def process(
        self,
        folders: str,
        definitions: str,
        if_wildcards,
        choice_separator: str,
        keep_choices_order: bool,
    ):
        options = {
            "wc_wildcards_folders": folders,
            "wc_wildcards_input": definitions,
            "wc_if_wildcards": if_wildcards,
            "wc_choice_separator": choice_separator,
            "wc_keep_choices_order": keep_choices_order,
        }
        return (options,)


class PromptPostProcessorSTNOptionsComfyUINode:
    """
    Node for Send-To-Negative options.
    """

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "separator": (
                    "STRING",
                    {
                        "default": PromptPostProcessor.DEFAULT_STN_SEPARATOR,
                        "tooltip": "Separator for the content added to the negative prompt",
                        "dynamicPrompts": False,
                    },
                ),
                "ignore_repeats": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_STN_IGNORE_REPEATS,
                        "tooltip": "Ignore repeated content added to the negative prompt",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
            },
        }

    RETURN_TYPES = ("PPP_OPTIONS_STN",)
    RETURN_NAMES = ("options",)

    FUNCTION = "process"

    CATEGORY = "ACB"

    def process(
        self,
        separator: str,
        ignore_repeats: bool,
    ):
        options = {
            "stn_separator": separator,
            "stn_ignore_repeats": ignore_repeats,
        }
        return (options,)


class PromptPostProcessorCleanupOptionsComfyUINode:
    """
    Node for Cleanup options.
    """

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "extra_spaces": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_EXTRA_SPACES,
                        "tooltip": "Remove extra spaces",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "empty_constructs": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_EMPTY_CONSTRUCTS,
                        "tooltip": "Remove empty constructs",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "extra_separators": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_EXTRA_SEPARATORS,
                        "tooltip": "Remove extra separators",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "extra_separators_additional": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_EXTRA_SEPARATORS2,
                        "tooltip": "Remove extra separators (additional cases)",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "extra_separators_include_eol": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_EXTRA_SEPARATORS_INCLUDE_EOL,
                        "tooltip": "Extra separators options also remove EOLs",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "around_breaks": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_BREAKS,
                        "tooltip": "Cleanup around BREAKs",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "breaks_with_eol": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_BREAKS_EOL,
                        "tooltip": "Set BREAKs in their own line",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "around_ands": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_ANDS,
                        "tooltip": "Cleanup around ANDs",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "ands_with_eol": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_ANDS_EOL,
                        "tooltip": "Set ANDs in their own line",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "around_extranetwork_tags": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_EXTRANETWORK_TAGS,
                        "tooltip": "Clean up around extra network tags",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "merge_attention": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_MERGE_ATTENTION,
                        "tooltip": "Merge nested attention constructs",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
                "remove_extranetwork_tags": (
                    "BOOLEAN",
                    {
                        "default": PromptPostProcessor.DEFAULT_CUP_REMOVE_EXTRANETWORK_TAGS,
                        "tooltip": "Remove extra network tags",
                        "label_on": "Yes",
                        "label_off": "No",
                    },
                ),
            },
        }

    RETURN_TYPES = ("PPP_OPTIONS_CUP",)
    RETURN_NAMES = ("options",)

    FUNCTION = "process"

    CATEGORY = "ACB"

    def process(
        self,
        extra_spaces: bool,
        empty_constructs: bool,
        extra_separators: bool,
        extra_separators_additional: bool,
        extra_separators_include_eol: bool,
        around_breaks: bool,
        breaks_with_eol: bool,
        around_ands: bool,
        ands_with_eol: bool,
        around_extranetwork_tags: bool,
        merge_attention: bool,
        remove_extranetwork_tags: bool,
    ):
        options = {
            "cup_extra_spaces": extra_spaces,
            "cup_empty_constructs": empty_constructs,
            "cup_extra_separators": extra_separators,
            "cup_extra_separators2": extra_separators_additional,
            "cup_extra_separators_include_eol": extra_separators_include_eol,
            "cup_breaks": around_breaks,
            "cup_breaks_eol": breaks_with_eol,
            "cup_ands": around_ands,
            "cup_ands_eol": ands_with_eol,
            "cup_extranetwork_tags": around_extranetwork_tags,
            "cup_merge_attention": merge_attention,
            "cup_remove_extranetwork_tags": remove_extranetwork_tags,
        }
        return (options,)


class PromptPostProcessorENMappingOptionsComfyUINode:
    """
    Node for ExtraNetworks mapping options.
    """

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "folders": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Comma separated list of extranetwork mappings folders",
                        "dynamicPrompts": False,
                    },
                ),
                "definitions": (
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

    RETURN_TYPES = ("PPP_OPTIONS_EN",)
    RETURN_NAMES = ("options",)

    FUNCTION = "process"

    CATEGORY = "ACB"

    def process(
        self,
        folders: str,
        definitions: str,
    ):
        options = {
            "en_mappings_folders": folders,
            "en_mappings_input": definitions,
        }
        return (options,)


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


class PromptPostProcessorWildcardConcatComfyUINode:
    """
    Node for selecting and concatenating wildcards as a prompt.
    """

    NONE_OPTION = "(none)"
    _ppp = None
    # _state = None
    # _tree = None
    _wildcard_key_map: dict[str, str] = {}

    @classmethod
    def _ensure_wildcards(cls):
        if cls._ppp is None:
            lf = PromptPostProcessorLogFactory()
            cls._ppp = PromptPostProcessor(
                lf.log,
                {
                    "app": SUPPORTED_APPS.comfyui.value,
                    "models_path": folder_paths.models_dir,
                    "model_filename": "",
                    "model_class": "",
                    "property_base": None,
                },
                PPPStateOptions(debug_level=DEBUG_LEVEL.minimal),
                wildcards_obj=PPPWildcards(lf.log),
            )
        # We need to populate the wildcard options in the tree to get the descriptions for the dropdown labels
        cls._ppp.state.wildcards_obj.refresh_wildcards(cls._ppp.state.options.debug_level, _resolve_wildcards_folders())
        cls._ppp.init_wildcards_options()
        return cls._ppp.state.wildcards_obj

    @classmethod
    def get_wildcard_keys(cls, filter_prefix=""):
        wc_obj = cls._ensure_wildcards()
        keys = sorted(wc_obj.wildcards.keys())
        if filter_prefix:
            keys = [k for k in keys if k.startswith(filter_prefix)]
        cls._wildcard_key_map = {cls.NONE_OPTION: cls.NONE_OPTION}
        labels = []
        for k in keys:
            wc = wc_obj.wildcards[k]
            pretty_key = k.replace("_", " ")
            desc = str(wc.options["description"]) if wc.options and "description" in wc.options else None
            label = f"{pretty_key} ({desc})" if desc else pretty_key
            labels.append(label)
            cls._wildcard_key_map[label] = k
        return [cls.NONE_OPTION] + labels

    @classmethod
    def INPUT_TYPES(cls):
        wc_list = cls.get_wildcard_keys()
        return {
            "required": {
                "filter": (
                    "STRING",
                    {
                        "default": "build",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "tooltip": "Filter wildcards by prefix (changing this refreshes the dropdowns)",
                    },
                ),
                "separator": (
                    "STRING",
                    {
                        "default": ", ",
                        "multiline": False,
                        "dynamicPrompts": False,
                        "tooltip": "Separator used to concatenate the selected wildcard references",
                    },
                ),
                "wildcard_1": (wc_list, {"tooltip": "Wildcard 1"}),
                "wildcard_2": (wc_list, {"tooltip": "Wildcard 2"}),
                "wildcard_3": (wc_list, {"tooltip": "Wildcard 3"}),
                "wildcard_4": (wc_list, {"tooltip": "Wildcard 4"}),
                "wildcard_5": (wc_list, {"tooltip": "Wildcard 5"}),
                "wildcard_6": (wc_list, {"tooltip": "Wildcard 6"}),
                "wildcard_7": (wc_list, {"tooltip": "Wildcard 7"}),
                "wildcard_8": (wc_list, {"tooltip": "Wildcard 8"}),
                "wildcard_9": (wc_list, {"tooltip": "Wildcard 9"}),
                "wildcard_10": (wc_list, {"tooltip": "Wildcard 10"}),
            },
            "optional": {
                "previous_prompt": (
                    "STRING",
                    {
                        "forceInput": True,
                        "tooltip": "Connect to the prompt output of another Wildcard Concat node to chain more than 10 wildcards",
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)

    FUNCTION = "process"

    CATEGORY = "ACB"

    def process(
        self,
        filter,  # noqa: A002  # pylint: disable=redefined-builtin, unused-argument
        separator,
        wildcard_1,
        wildcard_2,
        wildcard_3,
        wildcard_4,
        wildcard_5,
        wildcard_6,
        wildcard_7,
        wildcard_8,
        wildcard_9,
        wildcard_10,
        previous_prompt=None,
    ):
        key_map = self.__class__._wildcard_key_map  # pylint: disable=protected-access
        parts = [
            f"__{key_map.get(w, w)}__"
            for w in [
                wildcard_1,
                wildcard_2,
                wildcard_3,
                wildcard_4,
                wildcard_5,
                wildcard_6,
                wildcard_7,
                wildcard_8,
                wildcard_9,
                wildcard_10,
            ]
            if w != self.NONE_OPTION
        ]
        result = separator.join(parts)
        if previous_prompt:
            result = previous_prompt + separator + result if result else previous_prompt
        return (result,)


try:
    from server import PromptServer  # type: ignore
    from aiohttp import web as _aiohttp_web  # type: ignore

    @PromptServer.instance.routes.get("/acb_ppp/wildcards")
    async def _acb_ppp_get_wildcards(request):
        filter_prefix = request.rel_url.query.get("filter", "")
        wc_list = PromptPostProcessorWildcardConcatComfyUINode.get_wildcard_keys(filter_prefix)
        return _aiohttp_web.json_response({"wildcards": wc_list})

except Exception:  # pylint: disable=broad-except
    pass
