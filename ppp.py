import logging
import math
import os
import re
import textwrap
import time

from collections import namedtuple
from enum import Enum
from typing import Any, Callable, Optional
import lark
import numpy as np
import yaml

from ppp_hosts import SUPPORTED_APPS  # pylint: disable=import-error
from ppp_logging import DEBUG_LEVEL  # pylint: disable=import-error
from ppp_wildcards import PPPWildcard, PPPWildcards  # pylint: disable=import-error
from ppp_enmappings import PPPENMappingVariant, PPPExtraNetworkMappings  # pylint: disable=import-error


class PPPInterrupt(Exception):
    """
    Custom exception to handle interruptions in the PromptPostProcessor.
    This exception can be raised to stop the processing of prompts.
    """

    def __init__(self, message: str = "Processing interrupted.", pos_prefix: str = "", neg_prefix: str = ""):
        super().__init__(message)
        self.message = message
        self.pos_prefix = pos_prefix
        self.neg_prefix = neg_prefix


class PromptPostProcessor:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """
    The PromptPostProcessor class is responsible for processing and manipulating prompt strings.
    """

    @staticmethod
    def get_version_from_pyproject() -> str:
        """
        Reads the version from the pyproject.toml file.

        Returns:
            str: The version string.
        """
        version_str = "0.0.0"
        try:
            pyproject_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "pyproject.toml")
            with open(pyproject_path, "r", encoding="utf-8") as file:
                for line in file:
                    if line.startswith("version = "):
                        version_str = line.split("=")[1].strip().strip('"')
                        break
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.getLogger().exception(e)
        return version_str

    NAME = "Prompt Post-Processor"
    VERSION = get_version_from_pyproject()

    class IFWILDCARDS_CHOICES(Enum):
        ignore = "ignore"
        remove = "remove"
        warn = "warn"
        stop = "stop"

    class ONWARNING_CHOICES(Enum):
        warn = "warn"
        stop = "stop"

    DEFAULT_DEBUG_LEVEL = DEBUG_LEVEL.minimal.value
    DEFAULT_ONWARNING = ONWARNING_CHOICES.warn.value
    DEFAULT_STN_SEPARATOR = ", "
    DEFAULT_STN_IGNORE_REPEATS = True
    DEFAULT_WC_PROCESS = True
    DEFAULT_IF_WILDCARDS = IFWILDCARDS_CHOICES.stop.value
    DEFAULT_CHOICE_SEPARATOR = ", "
    DEFAULT_KEEP_CHOICES_ORDER = True
    DEFAULT_DO_CLEANUP = True
    DEFAULT_CLEANUP_VARIABLES = True
    DEFAULT_CUP_EXTRA_SPACES = True
    DEFAULT_CUP_EMPTY_CONSTRUCTS = True
    DEFAULT_CUP_EXTRA_SEPARATORS = True
    DEFAULT_CUP_EXTRA_SEPARATORS2 = True
    DEFAULT_CUP_EXTRA_SEPARATORS_INCLUDE_EOL = False
    DEFAULT_CUP_BREAKS = False
    DEFAULT_CUP_BREAKS_EOL = False
    DEFAULT_CUP_ANDS = False
    DEFAULT_CUP_ANDS_EOL = False
    DEFAULT_CUP_EXTRANETWORK_TAGS = False
    DEFAULT_CUP_MERGE_ATTENTION = True
    DEFAULT_CUP_REMOVE_EXTRANETWORK_TAGS = False
    WILDCARD_WARNING = '(WARNING TEXT "INVALID WILDCARD" IN BRIGHT RED:1.5)\nBREAK '
    WILDCARD_STOP = "INVALID WILDCARD! {0}\nBREAK "
    UNPROCESSED_STOP = "UNPROCESSED CONSTRUCTS!\nBREAK "
    INVALID_CONTENT_STOP = "INVALID CONTENT! {0}\nBREAK "

    def __init__(
        self,
        logger: logging.Logger,
        interrupt: Optional[Callable],
        env_info: dict[str, Any],
        options: Optional[dict[str, Any]] = None,
        grammar_content: Optional[str] = None,
        wildcards_obj: PPPWildcards = None,
        extranetwork_mappings_obj: PPPExtraNetworkMappings = None,
    ):
        """
        Initializes the PPP object.

        Args:
            logger: The logger object.
            interrupt: The interrupt function.
            env_info: A dictionary with information for the environment and loaded model.
            options: Optional. The options dictionary for configuring PPP behavior.
            grammar_content: Optional. The grammar content to be used for parsing.
            wildcards_obj: Optional. The wildcards object to be used for processing wildcards.
            extranetwork_mappings_obj: Optional. The extranetwork mappings object to be used for processing.
        """
        self.logger = logger
        self.rng = np.random.default_rng()  # gets seeded on each process prompt call
        self.interrupt_callback = interrupt
        self.options = options
        self.env_info = env_info
        self.wildcard_obj = wildcards_obj
        self.extranetwork_mappings_obj = extranetwork_mappings_obj

        default_config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ppp_config.yaml.defaults")
        try:
            with open(default_config_file, "r", encoding="utf-8") as f:
                self.config: dict[str, Any] = yaml.safe_load(f)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.config = {}
            raise PPPInterrupt(f"Failed to load default configuration from '{default_config_file}'.") from exc
        validate_def_cfg = self.__validate_normalize_configuration(self.config, "default configuration file")
        if validate_def_cfg != 0:
            errmsg = "Default configuration file has errors. Please restore the default configuration file and, per instructions, use a copy to adapt it."
            if validate_def_cfg == 2:
                raise PPPInterrupt(errmsg)
            else:
                self.logger.warning(errmsg)

        user_config_file = self.env_info.get("ppp_config", "")
        user_config: dict[str, Any] = {}
        if isinstance(user_config_file, dict):
            user_config = user_config_file
            self.__validate_normalize_configuration(user_config, "forced configuration")
        else:
            if user_config_file == "":
                if self.env_info.get("app", "") == SUPPORTED_APPS.comfyui.value:
                    try:
                        import folder_paths  # pylint: disable=import-error # type: ignore

                        user_dir = folder_paths.get_user_directory()
                        if user_dir and os.path.isdir(user_dir):
                            user_config_file = os.path.join(user_dir, "default", "ppp_config.yaml")
                    except Exception:  # pylint: disable=broad-exception-caught
                        self.logger.warning("Failed to get user directory for PPP config.")
                if not user_config_file or not os.path.exists(user_config_file):
                    user_config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ppp_config.yaml")
            if user_config_file and os.path.exists(user_config_file):
                with open(user_config_file, "r", encoding="utf-8") as f:
                    user_config = yaml.safe_load(f)
            self.__validate_normalize_configuration(user_config, "user configuration")
        self.__merge_configuration(user_config)

        self.models_config: dict[str, dict[str, Any] | None] = self.config.get("models") or {}
        self.known_models: list[str] = list(self.models_config.keys())

        # Patch for tests (copy comfyui)
        if self.env_info.get("app", "") == "tests":
            self.config.setdefault("hosts", {}).setdefault("tests", {})
            for m in self.known_models:
                self.models_config.setdefault(m, {}).setdefault("detect", {})["tests"] = (
                    self.models_config[m].get("detect", {}).get("comfyui", None)
                )

        self.host_config: dict[str, Any] = (self.config.get("hosts") or {}).get(self.env_info.get("app", ""))
        if self.host_config is None:
            raise PPPInterrupt(
                f"No host configuration found for app '{self.env_info.get('app', '')}'. Please check your configuration."
            )

        # Update env_info with model detection
        prop_base = self.env_info.get("property_base", None)
        model_class = self.env_info.get("model_class", "")
        for m in self.known_models:
            self.env_info["is_" + m] = False
            model_config = (self.models_config.get(m) or {}).get("detect", {}).get(self.env_info.get("app", ""), {})
            if model_config is not None:
                cls_list = model_config.get("class", [])
                if model_class in cls_list:
                    self.env_info["is_" + m] = True
                elif "property" in model_config and prop_base is not None:
                    prop = model_config["property"]
                    attr = getattr(prop_base, prop, None)
                    if isinstance(attr, bool) and attr:
                        self.env_info["is_" + m] = True

        # General options
        self.debug_level = DEBUG_LEVEL(self.options.get("debug_level", self.DEFAULT_DEBUG_LEVEL))
        self.gen_onwarning = self.ONWARNING_CHOICES(self.options.get("on_warning", self.DEFAULT_ONWARNING))
        self.variants_definitions = {}
        for m in self.known_models:
            for v, vo in (((self.models_config or {}).get(m) or {}).get("variants") or {}).items():
                if v not in self.known_models:
                    self.variants_definitions[v] = (m, vo["find_in_filename"])
                else:
                    self.logger.warning(
                        f"Variant name '{v}' in model '{m}' conflicts with a known model name. Discarding variant."
                    )

        if self.debug_level != DEBUG_LEVEL.none:
            self.logger.debug(self.format_output(f"Host configuration: {self.host_config}"))
        # Wildcards options
        self.wil_process_wildcards = self.options.get("process_wildcards", self.DEFAULT_WC_PROCESS)
        self.wil_keep_choices_order = self.options.get("keep_choices_order", self.DEFAULT_KEEP_CHOICES_ORDER)
        self.wil_choice_separator = self.options.get("choice_separator", self.DEFAULT_CHOICE_SEPARATOR)
        self.wil_ifwildcards = self.IFWILDCARDS_CHOICES(self.options.get("if_wildcards", self.DEFAULT_IF_WILDCARDS))
        # Send to negative options
        self.stn_ignore_repeats = self.options.get("stn_ignore_repeats", self.DEFAULT_STN_IGNORE_REPEATS)
        self.stn_separator = self.options.get("stn_separator", self.DEFAULT_STN_SEPARATOR)
        # Cleanup and remove options
        self.cup_do_cleanup = self.options.get("do_cleanup", self.DEFAULT_DO_CLEANUP)
        self.cup_cleanup_variables = self.options.get("cleanup_variables", self.DEFAULT_CLEANUP_VARIABLES)
        self.cup_extraspaces = self.cup_do_cleanup and self.options.get(
            "cleanup_extra_spaces", self.DEFAULT_CUP_EXTRA_SPACES
        )
        self.cup_emptyconstructs = self.cup_do_cleanup and self.options.get(
            "cleanup_empty_constructs", self.DEFAULT_CUP_EMPTY_CONSTRUCTS
        )
        self.cup_extraseparators = self.cup_do_cleanup and self.options.get(
            "cleanup_extra_separators", self.DEFAULT_CUP_EXTRA_SEPARATORS
        )
        self.cup_extraseparators2 = self.cup_do_cleanup and self.options.get(
            "cleanup_extra_separators2", self.DEFAULT_CUP_EXTRA_SEPARATORS2
        )
        self.cup_extraseparators_include_eol = self.cup_do_cleanup and self.options.get(
            "cleanup_extra_separators_include_eol", self.DEFAULT_CUP_EXTRA_SEPARATORS_INCLUDE_EOL
        )
        self.cup_breaks = self.cup_do_cleanup and self.options.get("cleanup_breaks", self.DEFAULT_CUP_BREAKS)
        self.cup_breaks_eol = self.cup_do_cleanup and self.options.get(
            "cleanup_breaks_eol", self.DEFAULT_CUP_BREAKS_EOL
        )
        self.cup_ands = self.cup_do_cleanup and self.options.get("cleanup_ands", self.DEFAULT_CUP_ANDS)
        self.cup_ands_eol = self.cup_do_cleanup and self.options.get("cleanup_ands_eol", self.DEFAULT_CUP_ANDS_EOL)
        self.cup_extranetworktags = self.cup_do_cleanup and self.options.get(
            "cleanup_extranetwork_tags", self.DEFAULT_CUP_EXTRANETWORK_TAGS
        )
        self.cup_mergeattention = self.cup_do_cleanup and self.options.get(
            "cleanup_merge_attention", self.DEFAULT_CUP_MERGE_ATTENTION
        )
        self.rem_removeextranetworktags = self.cup_do_cleanup and self.options.get(
            "remove_extranetwork_tags", self.DEFAULT_CUP_REMOVE_EXTRANETWORK_TAGS
        )

        # if self.debug_level != DEBUG_LEVEL.none:
        #    self.logger.info(f"Detected environment info: {env_info}")

        # Process with lark (debug with https://www.lark-parser.org/ide/)
        if grammar_content is None:
            grammar_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "grammar.lark")
            with open(grammar_filename, "r", encoding="utf-8") as file:
                grammar_content = file.read()

        # Preprocess grammar content for conditional compilation
        self.parser_full_only_old = lark.Lark(
            self.__preprocess_grammar(
                grammar_content,
                {
                    "ALLOW_NEW_CONTENT": False,
                    "ALLOW_WILDCARDS": False,
                    "ALLOW_CHOICES": False,
                    "ALLOW_COMMVARS": False,
                },
            ),
            propagate_positions=True,
        )
        grammar_content_full = self.__preprocess_grammar(
            grammar_content,
            {
                "ALLOW_NEW_CONTENT": True,
                "ALLOW_WILDCARDS": True,
                "ALLOW_CHOICES": True,
                "ALLOW_COMMVARS": True,
            },
        )
        self.parser_complete_full = lark.Lark(
            grammar_content_full,
            propagate_positions=True,
        )
        self.parser_complete_wc_ch = lark.Lark(
            self.__preprocess_grammar(
                grammar_content,
                {
                    "ALLOW_NEW_CONTENT": True,
                    "ALLOW_WILDCARDS": True,
                    "ALLOW_CHOICES": True,
                    "ALLOW_COMMVARS": False,
                },
            ),
            propagate_positions=True,
        )
        self.parser_complete_wc_cv = lark.Lark(
            self.__preprocess_grammar(
                grammar_content,
                {
                    "ALLOW_NEW_CONTENT": True,
                    "ALLOW_WILDCARDS": True,
                    "ALLOW_CHOICES": False,
                    "ALLOW_COMMVARS": True,
                },
            ),
            propagate_positions=True,
        )
        self.parser_complete_ch_cv = lark.Lark(
            self.__preprocess_grammar(
                grammar_content,
                {
                    "ALLOW_NEW_CONTENT": True,
                    "ALLOW_WILDCARDS": False,
                    "ALLOW_CHOICES": True,
                    "ALLOW_COMMVARS": True,
                },
            ),
            propagate_positions=True,
        )
        self.parser_complete_wc = lark.Lark(
            self.__preprocess_grammar(
                grammar_content,
                {
                    "ALLOW_NEW_CONTENT": True,
                    "ALLOW_WILDCARDS": True,
                    "ALLOW_CHOICES": False,
                    "ALLOW_COMMVARS": False,
                },
            ),
            propagate_positions=True,
        )
        self.parser_complete_ch = lark.Lark(
            self.__preprocess_grammar(
                grammar_content,
                {
                    "ALLOW_NEW_CONTENT": True,
                    "ALLOW_WILDCARDS": False,
                    "ALLOW_CHOICES": True,
                    "ALLOW_COMMVARS": False,
                },
            ),
            propagate_positions=True,
        )
        self.parser_complete_cv = lark.Lark(
            self.__preprocess_grammar(
                grammar_content,
                {
                    "ALLOW_NEW_CONTENT": True,
                    "ALLOW_WILDCARDS": False,
                    "ALLOW_CHOICES": False,
                    "ALLOW_COMMVARS": True,
                },
            ),
            propagate_positions=True,
        )

        # Partial parsers
        self.parser_content = lark.Lark(
            grammar_content_full,
            propagate_positions=True,
            start="content",
        )
        self.parser_choice = lark.Lark(
            grammar_content_full,
            propagate_positions=True,
            start="choice",
        )
        self.parser_choicesoptions = lark.Lark(
            grammar_content_full,
            propagate_positions=True,
            start="choicesoptions",
        )
        self.parser_condition = lark.Lark(
            grammar_content_full,
            propagate_positions=True,
            start="condition",
        )
        self.parser_choicevalue = lark.Lark(
            grammar_content_full,
            propagate_positions=True,
            start="choicevalue",
        )
        self.__init_sysvars()
        self.user_variables = {}
        self.echoed_variables = {}

    def __merge_configuration(self, user_config):
        """
        Merges the user configuration into the default configuration.

        Args:
            user_config: The user configuration dictionary to merge.
        """
        if "hosts" in user_config:
            # Options are replaced by host
            for host_key, host_value in user_config["hosts"].items():
                self.config["hosts"].setdefault(host_key, {}).update(host_value)
        if "models" in user_config:
            for model_key, model_value in user_config["models"].items():
                # We independently update the detection and variants for each model in the user configuration
                usr_mdetect = model_value.get("detect", "")
                # Detections are replaced by host
                cfg_detect = self.config["models"].setdefault(model_key, {}).get("detect")
                if cfg_detect is not None:
                    for host, hdetect in usr_mdetect.items():
                        cfg_detect[host] = hdetect
                # Variants are fully replaced if specified
                usr_mvariants = model_value.get("variants", "")
                if usr_mvariants is None:
                    del self.config["models"].setdefault(model_key, {})["variants"]
                else:
                    self.config["models"].setdefault(model_key, {})["variants"] = usr_mvariants

    def __re_flags_from_list(self, flags_list: list[str]) -> int:
        flag_value = 0
        for flag in flags_list:
            if hasattr(re, flag):
                flag_value |= getattr(re, flag)
            else:
                return 0
        return flag_value

    def __validate_find_in_filename_element(
        self,
        where: str,
        model_key: str,
        variant_key: str,
        find_in_filename: str | dict,
    ) -> dict | None:
        if isinstance(find_in_filename, str):
            try:
                re.compile(find_in_filename, re.IGNORECASE)
                return {"regex": find_in_filename, "flags": re.IGNORECASE}
            except re.error:
                self.logger.warning(
                    f"{where.title()}: Invalid regex pattern for variant '{variant_key}' in model '{model_key}'. Discarding variant."
                )
        elif isinstance(find_in_filename, dict):
            regex = find_in_filename.get("regex", "")
            flags = find_in_filename.get("flags", [])
            if not isinstance(regex, str) or not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
                self.logger.warning(
                    f"{where.title()}: Invalid format for 'find_in_filename' for variant '{variant_key}' in model '{model_key}'. Discarding variant."
                )
            else:
                fl = self.__re_flags_from_list(flags)
                if fl == 0 and len(flags):
                    self.logger.warning(
                        f"{where.title()}: Invalid regex flags for variant '{variant_key}' in model '{model_key}'. Discarding variant."
                    )
                try:
                    re.compile(regex, fl)
                    return {"regex": regex, "flags": fl}
                except re.error:
                    self.logger.warning(
                        f"{where.title()}: Invalid regex pattern for variant '{variant_key}' in model '{model_key}'. Discarding variant."
                    )
        return None

    def __validate_normalize_configuration(self, cfg: dict[str, Any] | Any, where: str) -> int:
        """
        Validates the configuration dictionary and normalizes it.

        Args:
            cfg (dict): The configuration dictionary to validate.

        Returns:
            int: 0 if the configuration is valid, 1 if there are warnings, 2 if there are fatal errors.
        """
        fatal_errors = False
        if not isinstance(cfg, dict):
            self.logger.error(f"{where.capitalize()}: is not a dictionary.")
            fatal_errors = True
        else:
            if cfg.get("hosts") and not isinstance(cfg["hosts"], dict):
                self.logger.error(f"{where.capitalize()}: 'hosts' is not a valid dictionary.")
                fatal_errors = True
            if cfg.get("models") and not isinstance(cfg.get("models"), dict):
                self.logger.error(f"{where.capitalize()}: 'models' is not a valid dictionary.")
                fatal_errors = True
        if fatal_errors:
            return 2
        result = 0
        defcfg_hosts: dict[str, Any] = cfg.get("hosts", {})
        for host_key, host_value in dict(defcfg_hosts).items():
            if host_key not in SUPPORTED_APPS._value2member_map_:  # pylint: disable=protected-access
                self.logger.warning(f"{where.capitalize()}: Unsupported host '{host_key}'. Discarding host.")
                defcfg_hosts.pop(host_key, None)
                result = 1
            elif host_value is not None and (
                not isinstance(host_value, dict)
                or not all(k in ["attention", "scheduling", "alternation", "and", "break"] for k in host_value)
            ):
                self.logger.warning(f"{where.capitalize()}: Invalid format for host '{host_key}'. Discarding host.")
                defcfg_hosts.pop(host_key, None)
                result = 1
        defcfg_models: dict[str, Any] = cfg.get("models", {})
        for model_key, model_value in dict(defcfg_models).items():
            if (
                not isinstance(model_value, dict)
                or model_value.get("detect") is None
                or not isinstance(model_value["detect"], dict)
            ):
                self.logger.warning(f"{where.capitalize()}: Invalid format for model '{model_key}'. Discarding model.")
                defcfg_models.pop(model_key, None)
                result = 1
            else:
                defcfg_m_detect: dict[str, Any] = model_value["detect"]
                for host_key, host_value in dict(defcfg_m_detect).items():
                    if host_key not in SUPPORTED_APPS._value2member_map_:  # pylint: disable=protected-access
                        self.logger.warning(
                            f"{where.capitalize()}: Unsupported host '{host_key}' in 'detect' for model '{model_key}'. Discarding host."
                        )
                        defcfg_m_detect.pop(host_key, None)
                        result = 1
                    elif host_value is not None:
                        if not isinstance(host_value, dict):
                            self.logger.warning(
                                f"{where.capitalize()}: Invalid format for host '{host_key}' in 'detect' for model '{model_key}'. Discarding host."
                            )
                            defcfg_m_detect.pop(host_key, None)
                            result = 1
                        elif "class" in host_value:
                            if not isinstance(host_value["class"], list) or not all(
                                isinstance(c, str) for c in host_value["class"]
                            ):
                                self.logger.warning(
                                    f"{where.capitalize()}: Invalid format for 'class' in host '{host_key}' in 'detect' for model '{model_key}'. Discarding host."
                                )
                                defcfg_m_detect.pop(host_key, None)
                                result = 1
                        elif "property" in host_value:
                            if not isinstance(host_value["property"], str):
                                self.logger.warning(
                                    f"{where.capitalize()}: Invalid format for 'property' in host '{host_key}' in 'detect' for model '{model_key}'. Discarding host."
                                )
                                defcfg_m_detect.pop(host_key, None)
                                result = 1
                        else:
                            self.logger.warning(
                                f"{where.capitalize()}: Neither 'class' nor 'property' specified for host '{host_key}' in 'detect' for model '{model_key}'. Discarding host."
                            )
                            defcfg_m_detect.pop(host_key, None)
                            result = 1
                if "variants" in model_value:
                    if not isinstance(model_value["variants"], dict):
                        self.logger.warning(
                            f"{where.capitalize()}: Invalid format for 'variants' in model '{model_key}'. Discarding model."
                        )
                        defcfg_models.pop(model_key, None)
                        result = 1
                    else:
                        defcfg_m_variants: dict[str, Any] = model_value["variants"]
                        for variant_key, variant_value in dict(defcfg_m_variants).items():
                            if not isinstance(variant_key, str) or not variant_key.isidentifier():
                                self.logger.warning(
                                    f"{where.capitalize()}: Invalid variant name '{variant_key}' in model '{model_key}'. Discarding variant."
                                )
                                defcfg_m_variants.pop(variant_key, None)
                                result = 1
                            elif not isinstance(variant_value, dict) or not isinstance(
                                variant_value.get("find_in_filename"), (str, dict, list)
                            ):
                                self.logger.warning(
                                    f"{where.capitalize()}: Invalid format for variant '{variant_key}' in model '{model_key}'. Discarding variant."
                                )
                                defcfg_m_variants.pop(variant_key, None)
                                result = 1
                            else:
                                if isinstance(variant_value["find_in_filename"], list):
                                    normalized_list = []
                                    for elem in variant_value["find_in_filename"]:
                                        validated_elem = self.__validate_find_in_filename_element(
                                            where, model_key, variant_key, elem
                                        )
                                        if validated_elem is not None:
                                            normalized_list.append(validated_elem)
                                    if len(normalized_list) != len(variant_value["find_in_filename"]):
                                        defcfg_m_variants.pop(variant_key, None)
                                        result = 1
                                    else:
                                        variant_value["find_in_filename"] = normalized_list
                                else:
                                    variant_value["find_in_filename"] = [
                                        self.__validate_find_in_filename_element(
                                            where, model_key, variant_key, variant_value["find_in_filename"]
                                        )
                                    ]
        return result

    def envinfo_hash(self) -> str:
        """
        Generates a hash string based on the environment information.

        Returns:
            str: A hash string representing the environment information.
        """
        return hash(tuple(sorted(self.env_info.items())))

    def options_hash(self) -> str:
        """
        Generates a hash string based on the options.

        Returns:
            str: A hash string representing the options.
        """
        return hash(tuple(sorted(self.options.items())))

    def __preprocess_grammar(self, grammar_content: str, options: dict[str, bool]) -> str:
        """
        Preprocesses the grammar content to handle conditional compilation directives.

        Args:
            grammar_content (str): The raw grammar content.
            options (dict[str,bool]): Options for preprocessing.

        Returns:
            str: The preprocessed grammar content.
        """
        lines = grammar_content.split("\n")
        result_lines = []
        skip_current_block = []
        all_blocks_skipped = []

        def evaluate_conditions(conditions: list[str]) -> bool:
            """
            Evaluates the conditions based on the provided options. Allows for negation with '!' prefix.

            Args:
                conditions (list[str]): List of conditions to evaluate.

            Returns:
                bool: True if all conditions are met, False otherwise.
            """
            r = True
            for condition in conditions:
                if condition.startswith("!"):
                    r = r and not options.get(condition[1:], False)
                else:
                    r = r and options.get(condition, True)
            return r

        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith("//#if"):
                # Extract condition from the #if directive
                conditions = stripped_line[5:].strip().split(" ")
                # Evaluate the conditions
                skip_current_block.append(not evaluate_conditions(conditions))
                all_blocks_skipped.append(skip_current_block[-1])
                continue
            if stripped_line.startswith("//#elif"):
                if not skip_current_block:
                    self.logger.warning("Unmatched //#elif directive found in grammar content.")
                elif all_blocks_skipped[-1]:
                    # Extract condition from the #elif directive
                    conditions = stripped_line[7:].strip().split(" ")
                    # Evaluate the conditions
                    skip_current_block[-1] = not evaluate_conditions(conditions)
                    if not skip_current_block[-1]:
                        all_blocks_skipped[-1] = False
                else:
                    skip_current_block[-1] = True
                continue
            if stripped_line.startswith("//#else"):
                if not skip_current_block:
                    self.logger.warning("Unmatched //#else directive found in grammar content.")
                elif all_blocks_skipped[-1]:
                    skip_current_block[-1] = False
                else:
                    skip_current_block[-1] = True
                continue
            if stripped_line.startswith("//#endif"):
                if not skip_current_block:
                    self.logger.warning("Unmatched //#endif directive found in grammar content.")
                else:
                    skip_current_block.pop()
                    all_blocks_skipped.pop()
                continue
            # Include the line if we're not skipping any current block
            if not any(skip_current_block):
                result_lines.append(stripped_line)
        # Check for unclosed blocks at the end
        if skip_current_block:
            self.logger.warning(
                f"Found {len(skip_current_block)} unclosed conditional directive(s) at the end of the file"
            )
        return "\n".join(result_lines)

    def interrupt(self):
        if self.interrupt_callback is not None:
            self.interrupt_callback()

    def format_output(self, text: str) -> str:
        """
        Formats the output text by encoding it using unicode_escape and decoding it using utf-8.

        Args:
            text (str): The input text to be formatted.

        Returns:
            str: The formatted output text.
        """
        return text.encode("unicode_escape").decode("utf-8")

    def __init_sysvars(self):
        """
        Initializes the system variables.
        """
        self.system_variables = {}
        sdchecks = {x: self.env_info.get("is_" + x, False) for x in self.known_models}
        sdchecks.update({"": True})
        self.system_variables["_model"] = next((k for k, v in sdchecks.items() if v), "")
        self.system_variables["_sd"] = self.system_variables["_model"]  # deprecated
        model_filename = self.env_info.get("model_filename", "")
        self.system_variables["_sdfullname"] = model_filename  # deprecated
        self.system_variables["_modelfullname"] = model_filename
        self.system_variables["_sdname"] = os.path.basename(model_filename)  # deprecated
        self.system_variables["_modelname"] = os.path.basename(model_filename)
        self.system_variables["_modelclass"] = self.env_info.get("model_class", "")
        is_models = {}
        for model_name, model_type_and_substrings in self.variants_definitions.items():
            if not (model_type_and_substrings[0] == "" or sdchecks.get(model_type_and_substrings[0], False)):
                is_models[model_name] = False
            else:
                is_models[model_name] = any(
                    (re.search(dre["regex"], model_filename, dre["flags"]) is not None)
                    for dre in model_type_and_substrings[1]
                )
        is_models_true = [k for k, v in is_models.items() if v]
        if len(is_models_true) > 1:
            self.logger.warning(
                f"Multiple model variants detected at the same time in the filename!: {', '.join(is_models_true)}"
            )
        self.system_variables.update({"_is_" + x: y for x, y in is_models.items()})
        for x in sdchecks.keys():
            if x != "":
                self.system_variables["_is_" + x] = sdchecks[x]
                self.system_variables["_is_pure_" + x] = sdchecks[x] and not any(is_models.values())
                self.system_variables["_is_variant_" + x] = sdchecks[x] and any(is_models.values())
        # special cases
        self.system_variables["_is_sd"] = sdchecks["sd1"] or sdchecks["sd2"] or sdchecks["sdxl"] or sdchecks["sd3"]
        is_ssd = self.env_info.get("is_ssd", False)
        self.system_variables["_is_ssd"] = is_ssd
        self.system_variables["_is_sdxl_no_ssd"] = sdchecks["sdxl"] and not is_ssd
        # backcompatibility (but the modern one to use would be _is_pure_sdxl)
        self.system_variables["_is_sdxl_no_pony"] = sdchecks["sdxl"] and not self.system_variables.get(
            "_is_pony", False
        )

    def __add_to_insertion_points(
        self, negative_prompt: str, add_at_insertion_point: list[str], insertion_at: list[tuple[int, int]]
    ) -> str:
        """
        Adds the negative prompt to the insertion points.

        Args:
            negative_prompt (str): The negative prompt to be added.
            add_at_insertion_point (list): A list of insertion points.
            insertion_at (list): A list of insertion blocks.

        Returns:
            str: The modified negative prompt.
        """
        ordered_range = sorted(
            range(10), key=lambda x: insertion_at[x][0] if insertion_at[x] is not None else float("-inf"), reverse=True
        )
        for n in ordered_range:
            if insertion_at[n] is not None:
                ipp = insertion_at[n][0]
                ipl = insertion_at[n][1] - insertion_at[n][0]
                if negative_prompt[ipp - len(self.stn_separator) : ipp] == self.stn_separator:
                    ipp -= len(self.stn_separator)  # adjust for existing start separator
                    ipl += len(self.stn_separator)
                add_at_insertion_point[n].insert(0, negative_prompt[:ipp])
                if negative_prompt[ipp + ipl : ipp + ipl + len(self.stn_separator)] == self.stn_separator:
                    ipl += len(self.stn_separator)  # adjust for existing end separator
                endPart = negative_prompt[ipp + ipl :]
                if len(endPart) > 0:
                    add_at_insertion_point[n].append(endPart)
                negative_prompt = self.stn_separator.join(add_at_insertion_point[n])
            else:
                ipp = 0
                if negative_prompt.startswith(self.stn_separator):
                    ipp = len(self.stn_separator)
                add_at_insertion_point[n].append(negative_prompt[ipp:])
                negative_prompt = self.stn_separator.join(add_at_insertion_point[n])
        return negative_prompt

    def __add_to_start(self, negative_prompt: str, add_at_start: list[str]) -> str:
        """
        Adds the elements in `add_at_start` list to the start of the `negative_prompt` string.

        Args:
            negative_prompt (str): The original negative prompt string.
            add_at_start (list): The list of elements to be added at the start of the negative prompt.

        Returns:
            str: The updated negative prompt string with the elements added at the start.
        """
        if len(negative_prompt) > 0:
            ipp = 0
            if negative_prompt.startswith(self.stn_separator):
                ipp = len(self.stn_separator)  # adjust for existing end separator
            add_at_start.append(negative_prompt[ipp:])
        negative_prompt = self.stn_separator.join(add_at_start)
        return negative_prompt

    def __add_to_end(self, negative_prompt: str, add_at_end: list[str]) -> str:
        """
        Adds the elements in `add_at_end` list to the end of `negative_prompt` string.

        Args:
            negative_prompt (str): The original negative prompt string.
            add_at_end (list): The list of elements to be added at the end of `negative_prompt`.

        Returns:
            str: The updated negative prompt string with elements added at the end.
        """
        if len(negative_prompt) > 0:
            ipl = len(negative_prompt)
            if negative_prompt.endswith(self.stn_separator):
                ipl -= len(self.stn_separator)  # adjust for existing start separator
            add_at_end.insert(0, negative_prompt[:ipl])
        negative_prompt = self.stn_separator.join(add_at_end)
        return negative_prompt

    def __cleanup(self, text: str, where: int = 0) -> str:
        """
        Trims the given text based on the specified cleanup options.

        Args:
            text (str): The text to be cleaned up.
            where (int): Indicates the context or position for cleanup (0=generic, -1=negative prompt, 1=positive prompt).

        Returns:
            str: The resulting text.
        """
        break_processing = self.host_config.get("break", "ok")
        # break_processing == "ok" (and always)
        if self.cup_breaks_eol:
            # replace spaces before break with EOL
            text = re.sub(r"[, ]+BREAK\b", "\nBREAK", text)
        if self.cup_breaks:
            # collapse separators and commas before BREAK
            text = re.sub(r"[, ]+BREAK\b", " BREAK", text)
            # collapse separators and commas after BREAK
            text = re.sub(r"\bBREAK[, ]+", "BREAK ", text)
            # collapse separators and commas around BREAK
            text = re.sub(r"[, ]+BREAK[, ]+", " BREAK ", text)
            # collapse BREAKs
            text = re.sub(r"\bBREAK(?:\s+BREAK)+\b", " BREAK ", text)
            # remove spaces between start of line and BREAK
            text = re.sub(r"^[ ]+BREAK\b", "BREAK", text, flags=re.MULTILINE)
            # remove spaces between BREAK and end of line
            text = re.sub(r"\bBREAK[ ]+$", "BREAK", text, flags=re.MULTILINE)
            # remove at start of prompt
            text = re.sub(r"\A(?:\s*BREAK\b\s*)+", "", text)
            # remove at end of prompt
            text = re.sub(r"(?:\s*\bBREAK\s*)+\Z", "", text)
        break_replacements = {
            "eol": ("replaced with EOL", "\n"),
            "comma": ("replaced with COMMA", ", "),
            "remove": ("removed", " "),
        }
        if break_processing in break_replacements.keys():
            text2 = re.sub(r"\b\s*BREAK\s*\b", break_replacements[break_processing][1], text)
            if text2 != text:
                text = text2
                if self.debug_level == DEBUG_LEVEL.full:
                    self.logger.debug(f"BREAK construct {break_replacements[break_processing][0]}")
        elif break_processing == "error":
            if re.search(r"\bBREAK\b", text):
                self.warn_or_stop(where == -1, "BREAK constructs are not allowed!")

        if self.cup_ands:
            # collapse ANDs with space after
            text = re.sub(r"\bAND(?:\s+AND)+\s+", "AND ", text)
            # collapse ANDs without space after
            text = re.sub(r"\bAND(?:\s+AND)+\b", "AND", text)
            # collapse separators and spaces before ANDs
            text = re.sub(r"[, ]+AND\b", " AND", text)
            # collapse separators and spaces after ANDs
            text = re.sub(r"\bAND[, ]+", "AND ", text)
            # remove at start of prompt
            text = re.sub(r"\A(?:AND\b\s*)+", "", text)
            # remove at end of prompt
            text = re.sub(r"(\s*\bAND)+\Z", "", text)

        escapedSeparator = re.escape(self.stn_separator)
        optwhitespace = r"\s*" if self.cup_extraseparators_include_eol else r"[ \t\v\f]*"
        optwhitespace_separator = optwhitespace + escapedSeparator + optwhitespace
        optwhitespace_comma = optwhitespace + "," + optwhitespace
        sep_options = [(optwhitespace_separator, self.stn_separator)]  # sendtonegative separator
        if optwhitespace_comma != optwhitespace_separator:
            sep_options.append((optwhitespace_comma, ", "))  # regular comma separator
        for sep, replacement in sep_options:
            if self.cup_extraseparators:
                # collapse separators
                text = re.sub(r"(?:" + sep + r"){2,}", replacement, text)
                # remove separator after starting parenthesis, starting bracket
                text = re.sub(
                    # r"(" + sep + r"[([]\s*)(?:" + sep + r")+",
                    r"([([]\s*)(?:" + sep + r")+",
                    r"\1",
                    text,
                )
                # remove separator before ending parenthesis, ending bracket
                text = re.sub(
                    # r"(?:" + sep + r")+(\s*[:)\]]" + sep + r")",
                    r"(?:" + sep + r")+(\s*[)\]])",
                    r"\1",
                    text,
                )
                # remove separator before colon
                text = re.sub(
                    r"(?:" + sep + r")+(\s*:" + sep + r")",
                    r"\1",
                    text,
                )
            if self.cup_extraseparators2:
                # remove at start of prompt or line
                text = re.sub(r"^(?:" + sep + r")+", "", text, flags=re.MULTILINE)
                # remove at end of prompt or line
                text = re.sub(r"(?:" + sep + r")+$", "", text, flags=re.MULTILINE)
        if self.cup_extranetworktags:
            # remove spaces before <
            text = re.sub(r"\B\s+<(?!!)", "<", text)
            # remove spaces after >
            text = re.sub(r">\s+\B", ">", text)
        if self.cup_extraspaces:
            # remove spaces before comma
            text = re.sub(r"[ ]+,", ",", text)
            # remove spaces at end of line
            text = re.sub(r"[ ]+$", "", text, flags=re.MULTILINE)
            # remove spaces at start of line
            text = re.sub(r"^[ ]+", "", text, flags=re.MULTILINE)
            # remove extra whitespace after starting parenthesis or bracket
            text = re.sub(r"([,\.;\s]+[([])\s+", r"\1", text)
            # remove extra whitespace before ending parenthesis or bracket
            text = re.sub(r"\s+([)\]][,\.;\s]+)", r"\1", text)
            # remove empty lines
            text = re.sub(r"(?:^|\n)[ ]*\n", "\n", text)
            text = re.sub(r"\n[ ]*\n$", "\n", text)
            # collapse spaces
            text = re.sub(r"[ ]{2,}", " ", text)
            # remove spaces at start and end
            text = text.strip()

        return text

    def __get_best_parser(self, prompt: str) -> tuple[lark.Lark, str]:
        """
        Checks the prompt and returns the best parser to use based on its content.

        Args:
            prompt (str): The prompt to check.

        Returns:
            tuple[lark.Lark, str]: The best parser and its description.
        """
        tests = {
            "ALLOW_WILDCARDS": re.search(r"(?<!\\)__", prompt) is not None,
            "ALLOW_CHOICES": re.search(r"(?<!\$\\)\{|\}", prompt) is not None,
            "ALLOW_COMMVARS": re.search(r"(?<!\\)(?:<ppp:|\$\{)", prompt) is not None,
        }
        if tests["ALLOW_WILDCARDS"] and tests["ALLOW_CHOICES"] and tests["ALLOW_COMMVARS"]:
            return (
                self.parser_complete_full,
                "full parser with wildcards, choices, commands and variables",
            )
        if tests["ALLOW_WILDCARDS"] and tests["ALLOW_CHOICES"]:
            return (
                self.parser_complete_wc_ch,
                "parser with wildcards and choices",
            )
        if tests["ALLOW_WILDCARDS"] and tests["ALLOW_COMMVARS"]:
            return (
                self.parser_complete_wc_cv,
                "parser with wildcards, commands and variables",
            )
        if tests["ALLOW_CHOICES"] and tests["ALLOW_COMMVARS"]:
            return (
                self.parser_complete_ch_cv,
                "parser with choices, commands and variables",
            )
        if tests["ALLOW_WILDCARDS"]:
            return (
                self.parser_complete_wc,
                "parser with wildcards",
            )
        if tests["ALLOW_CHOICES"]:
            return (
                self.parser_complete_ch,
                "parser with choices",
            )
        if tests["ALLOW_COMMVARS"]:
            return (
                self.parser_complete_cv,
                "parser with commands and variables",
            )
        return (
            self.parser_full_only_old,
            "simple parser without new constructs",
        )

    def __processprompts(self, prompt, negative_prompt):
        """
        Process the prompt and negative prompt.

        Args:
            prompt (str): The prompt.
            negative_prompt (str): The negative prompt.

        Returns:
            tuple: A tuple containing the processed prompt and negative prompt.
        """
        self.user_variables = {}
        self.echoed_variables = {}
        all_variables = {**self.system_variables}

        # Process prompt
        p_processor = self.TreeProcessor(self)
        (prompt_parser, parser_description) = self.__get_best_parser(prompt)
        if self.debug_level == DEBUG_LEVEL.full:
            self.logger.debug(f"Using {parser_description} for prompt")
        p_parsed = self.parse_prompt(
            "prompt",
            prompt,
            prompt_parser,
        )
        prompt = p_processor.start_visit("prompt", p_parsed, False)

        # Process negative prompt
        n_processor = self.TreeProcessor(self)
        (n_prompt_parser, n_parser_description) = self.__get_best_parser(negative_prompt)
        if self.debug_level == DEBUG_LEVEL.full:
            self.logger.debug(f"Using {n_parser_description} for negative prompt")
        n_parsed = self.parse_prompt(
            "negative prompt",
            negative_prompt,
            n_prompt_parser,
        )
        negative_prompt = n_processor.start_visit("negative prompt", n_parsed, True)

        # Complete variables
        var_keys = set(self.user_variables.keys()).union(set(self.echoed_variables.keys()))
        for k in var_keys:
            ev = self.echoed_variables.get(k)
            if ev is None:
                ev = self.user_variables.get(k)
            if ev is None or not isinstance(ev, str):
                if self.debug_level == DEBUG_LEVEL.full:
                    self.logger.debug(self.format_output(f"Completing variable: {k}"))
                ev = p_processor.get_final_user_variable(k)
            all_variables[k] = self.__cleanup(ev, 0) if self.cup_cleanup_variables else ev
        if self.debug_level == DEBUG_LEVEL.full:
            self.logger.debug(self.format_output(f"All variables: {all_variables}"))

        # Insertions in the negative prompt
        if self.debug_level == DEBUG_LEVEL.full:
            self.logger.debug(self.format_output(f"New negative additions: {p_processor.add_at}"))
            self.logger.debug(self.format_output(f"New negative indexes: {n_processor.insertion_at}"))
        negative_prompt = self.__add_to_insertion_points(
            negative_prompt, p_processor.add_at["insertion_point"], n_processor.insertion_at
        )
        if p_processor.add_at["start"]:
            negative_prompt = self.__add_to_start(negative_prompt, p_processor.add_at["start"])
        if p_processor.add_at["end"]:
            negative_prompt = self.__add_to_end(negative_prompt, p_processor.add_at["end"])

        # Clean up
        prompt = self.__cleanup(prompt, 1)
        negative_prompt = self.__cleanup(negative_prompt, -1)

        # Check for wildcards not processed
        foundP = bool(p_processor.detectedWildcards)
        foundNP = bool(n_processor.detectedWildcards)
        if foundP or foundNP:
            if self.wil_ifwildcards == self.IFWILDCARDS_CHOICES.stop:
                self.logger.error("Found unprocessed wildcards!")
            else:
                self.logger.info("Found unprocessed wildcards.")
            ppwl = ", ".join(p_processor.detectedWildcards)
            npwl = ", ".join(n_processor.detectedWildcards)
            if foundP:
                self.logger.error(self.format_output(f"In the positive prompt: {ppwl}"))
            if foundNP:
                self.logger.error(self.format_output(f"In the negative prompt: {npwl}"))
            if self.wil_ifwildcards == self.IFWILDCARDS_CHOICES.warn:
                prompt = self.WILDCARD_WARNING + prompt
            elif self.wil_ifwildcards == self.IFWILDCARDS_CHOICES.stop:
                raise PPPInterrupt(
                    "Found unprocessed wildcards!",
                    self.WILDCARD_STOP.format(ppwl) if foundP else "",
                    self.WILDCARD_STOP.format(npwl) if foundNP else "",
                )

        # Check for special character sequences that should not be in the result
        compound_prompt = prompt + "\n" + negative_prompt
        found_sequences = re.findall(r"::|\$\$|\$\{|[{}]", compound_prompt)
        if found_sequences:
            self.logger.warning(
                f"""Found probably invalid character sequences on the result ({', '.join(map(lambda x: '"' + x + '"', set(found_sequences)))}). Something might be wrong!"""
            )
        return prompt, negative_prompt, all_variables

    def process_prompt(
        self,
        original_prompt: str,
        original_negative_prompt: str,
        seed: int = 0,
    ):
        """
        Initializes the random number generator and processes the prompt and negative prompt.

        Args:
            original_prompt (str): The original prompt.
            original_negative_prompt (str): The original negative prompt.
            seed (int): The seed.

        Returns:
            tuple: A tuple containing the processed prompt, negative prompt and all the prompt variables.
        """
        all_variables = {}
        try:
            if seed == -1:
                seed = np.random.randint(0, 2**32, dtype=np.int64)
            self.rng = np.random.default_rng(seed & 0xFFFFFFFF)
            prompt = original_prompt
            negative_prompt = original_negative_prompt
            self.debug_level = DEBUG_LEVEL(self.options.get("debug_level", DEBUG_LEVEL.none.value))
            if self.debug_level != DEBUG_LEVEL.none:
                self.logger.info(f"System variables: {self.system_variables}")
                self.logger.info(f"Input seed: {seed}")
                self.logger.info(self.format_output(f"Input prompt: {prompt}"))
                self.logger.info(self.format_output(f"Input negative_prompt: {negative_prompt}"))
            t1 = time.monotonic_ns()
            prompt, negative_prompt, all_variables = self.__processprompts(prompt, negative_prompt)
            t2 = time.monotonic_ns()
            if self.debug_level != DEBUG_LEVEL.none:
                self.logger.info(self.format_output(f"Result prompt: {prompt}"))
                self.logger.info(self.format_output(f"Result negative_prompt: {negative_prompt}"))
                self.logger.info(f"Process prompt pair time: {(t2 - t1) / 1_000_000_000:.3f} seconds")

            # if self.debug_level != DEBUG_LEVEL.none:
            #     self.logger.debug(f"Wildcards memory usage: {self.wildcard_obj.__sizeof__()}")
            # Check for constructs not processed due to parsing problems
            fullcontent: str = prompt + negative_prompt
            if fullcontent.find("<ppp:") >= 0:
                raise PPPInterrupt(
                    "Found unprocessed constructs!",
                    self.UNPROCESSED_STOP if prompt.find("<ppp:") >= 0 else "",
                    self.UNPROCESSED_STOP if negative_prompt.find("<ppp:") >= 0 else "",
                )
            return prompt, negative_prompt, all_variables
        except PPPInterrupt as e:
            self.logger.error(e.message)
            if e.pos_prefix:
                prompt = e.pos_prefix + prompt
            if e.neg_prefix:
                negative_prompt = e.neg_prefix + negative_prompt
            self.logger.error("Interrupting!")
            self.interrupt()
            return prompt, negative_prompt, all_variables
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.exception(e)
            return original_prompt, original_negative_prompt, all_variables

    def parse_prompt(self, prompt_description: str, prompt: str, parser: lark.Lark, raise_parsing_error: bool = False):
        """
        Parses a prompt using the specified parser.

        Args:
            prompt_description (str): The description of the prompt.
            prompt (str): The prompt to be parsed.
            parser (lark.Lark): The parser to be used.
            raise_parsing_error (bool): Whether to raise a parsing error.

        Returns:
            Tree: The parsed prompt.
        """
        t1 = time.monotonic_ns()
        parsed_prompt = None
        try:
            if self.debug_level == DEBUG_LEVEL.full:
                self.logger.debug(self.format_output(f"Parsing {prompt_description}: '{prompt}'"))
            parsed_prompt = parser.parse(prompt)
            # we store the contents so we can use them later even if the meta position is not valid anymore
            if isinstance(parsed_prompt, lark.Tree):
                for n in parsed_prompt.iter_subtrees():
                    if isinstance(n, lark.Tree):
                        if n.meta.empty:
                            n.meta.content = ""
                        else:
                            n.meta.content = prompt[n.meta.start_pos : n.meta.end_pos]
        except lark.exceptions.UnexpectedInput:
            if raise_parsing_error:
                raise
            self.logger.exception(self.format_output(f"Parsing failed on prompt!: {prompt}"))
        t2 = time.monotonic_ns()
        if self.debug_level == DEBUG_LEVEL.full:
            self.logger.debug(f"Parse {prompt_description} time: {(t2 - t1) / 1_000_000_000:.3f} seconds")
            if parsed_prompt:
                self.logger.debug(
                    "Tree:\n"
                    + textwrap.indent(
                        re.sub(
                            r"\n$",
                            "",
                            parsed_prompt.pretty() if isinstance(parsed_prompt, lark.Tree) else parsed_prompt,
                        ),
                        "    ",
                    )
                )
        return parsed_prompt

    def warn_or_stop(self, is_negative: bool, message: str, e: Exception = None):
        if self.gen_onwarning == self.ONWARNING_CHOICES.stop:
            raise PPPInterrupt(
                message,
                self.INVALID_CONTENT_STOP.format(message) if not is_negative else "",
                self.INVALID_CONTENT_STOP.format(message) if is_negative else "",
            ) from e
        self.logger.warning(message)

    class TreeProcessor(lark.visitors.Interpreter):
        """
        A class for interpreting and processing a tree generated by the prompt parser.

        Args:
            ppp (PromptPostProcessor): The PromptPostProcessor object.

        Attributes:
            add_at (dict): The dictionary to store the content to be added at different positions of the negative prompt.
            insertion_at (list): The list of insertion points in the negative prompt.
            detectedWildcards (list): The list of detected invalid wildcards or choices.
            result (str): The final processed prompt.
        """

        def __init__(self, ppp: "PromptPostProcessor"):
            super().__init__()
            self.__ppp = ppp
            self.AccumulatedShell = namedtuple("AccumulatedShell", ["type", "data"])
            self.NegTag = namedtuple("NegTag", ["start", "end", "content", "parameters", "shell"])
            self.__shell: list[self.AccumulatedShell] = []  # type: ignore
            self.__negtags: list[self.NegTag] = []  # type: ignore
            self.__already_processed: list[str] = []
            self.__is_negative = False
            self.__wildcard_filters = {}
            self.__seen_wildcards: list[str] = []
            self.add_at: dict = {"start": [], "insertion_point": [[] for x in range(10)], "end": []}
            self.insertion_at: list[tuple[int, int]] = [None for x in range(10)]
            self.detectedWildcards: list[str] = []
            self.result = ""

        def warn_or_stop(self, message: str, e: Exception = None):
            self.__ppp.warn_or_stop(self.__is_negative, message, e)

        def start_visit(self, prompt_description: str, parsed_prompt: lark.Tree, is_negative: bool = False) -> str:
            """
            Start the visit process.

            Args:
                prompt_description (str): The description of the prompt.
                parsed_prompt (Tree): The parsed prompt.
                is_negative (bool): Whether the prompt is negative or not.

            Returns:
                str: The processed prompt.
            """
            t1 = time.monotonic_ns()
            self.__is_negative = is_negative
            if self.__ppp.debug_level != DEBUG_LEVEL.none:
                self.__ppp.logger.info(f"Processing {prompt_description}...")
            self.visit(parsed_prompt)
            t2 = time.monotonic_ns()
            if self.__ppp.debug_level != DEBUG_LEVEL.none:
                self.__ppp.logger.info(f"Process {prompt_description} time: {(t2 - t1) / 1_000_000_000:.3f} seconds")
            return self.result

        def __visit(
            self,
            node: lark.Tree | lark.Token | list[lark.Tree | lark.Token] | None,
            restore_state: bool = False,
            discard_content: bool = False,
        ) -> str:
            """
            Visit a node in the tree and process it or accumulate its value if it is a Token.

            Args:
                node (Tree|Token|list): The node or list of nodes to visit.
                restore_state (bool): Whether to restore the state after visiting the node.
                discard_content (bool): Whether to discard the content of the node.

            Returns:
                str: The result of the visit.
            """
            backup_result = self.result
            if restore_state:
                backup_shell = self.__shell.copy()
                backup_negtags = self.__negtags.copy()
                backup_already_processed = self.__already_processed.copy()
                backup_add_at = self.add_at.copy()
                backup_insertion_at = self.insertion_at.copy()
                backup_detectedwildcards = self.detectedWildcards.copy()
            if node is not None:
                if isinstance(node, list):
                    for child in node:
                        self.__visit(child)
                elif isinstance(node, lark.Tree):
                    self.visit(node)
                elif isinstance(node, lark.Token):
                    self.result += node
            len_backup = len(backup_result)
            # if self.result[:len_backup] == backup_result:  # this is only necessary if we call parse_prompt with a parser from "start", because it resets the result
            added_result = self.result[len_backup:]
            # else:
            #     added_result = self.result
            if discard_content or restore_state:
                self.result = backup_result
            if restore_state:
                self.__shell = backup_shell
                self.__negtags = backup_negtags
                self.__already_processed = backup_already_processed
                self.add_at = backup_add_at
                self.insertion_at = backup_insertion_at
                self.detectedWildcards = backup_detectedwildcards
            return added_result

        def __get_original_node_content(self, node: lark.Tree | lark.Token, default=None) -> str:
            """
            Get the original content of a node.

            Args:
                node (Tree|Token): The node to get the content from.
                default: The default value to return if the content is not found.

            Returns:
                str: The original content of the node.
            """
            return (
                node.meta.content
                if hasattr(node, "meta") and node.meta is not None and not node.meta.empty
                else default
            )

        def __get_user_variable_value(self, name: str, evaluate=True, visit=False) -> str:
            """
            Get the value of a user variable.

            Args:
                name (str): The name of the user variable.
                evaluate (bool): Whether to evaluate the variable.
                visit (bool): Whether to also visit the variable (add to result).

            Returns:
                str: The value of the user variable.
            """
            v = self.__ppp.user_variables.get(name, None)
            if v is not None:
                visited = False
                if isinstance(v, lark.Tree):
                    if evaluate:
                        v = self.__visit(v, not visit)
                        visited = visit
                    else:
                        v = self.__get_original_node_content(v, "not evaluated yet")
                if visit and not visited:
                    self.result += v
            return v

        def get_final_user_variable(self, name: str) -> str:
            return self.__get_user_variable_value(name, True, False)

        def __set_user_variable_value(self, name: str, value: str):
            """
            Set the value of a user variable.

            Args:
                name (str): The name of the user variable.
                value (str): The value to be set.
            """
            self.__ppp.user_variables[name] = value

        def __remove_user_variable(self, name: str):
            """
            Remove a user variable.

            Args:
                name (str): The name of the user variable.
            """
            if name in self.__ppp.user_variables:
                del self.__ppp.user_variables[name]

        def __debug_end(self, construct: str, start_result: str, duration: int, info=None):
            """
            Log the end of a construct processing.

            Args:
                construct (str): The name of the construct.
                start_result (str): The initial result.
                duration (int): The duration of the processing in ns.
                info: Additional information to log.
            """
            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                info = f"({info}) " if info is not None and info != "" else ""
                output = self.result[len(start_result) :]
                if output != "":
                    output = f" >> '{output}'"
                self.__ppp.logger.debug(
                    self.__ppp.format_output(
                        f"TreeProcessor.{construct} {info}({duration / 1_000_000_000:.3f} seconds){output}"
                    )
                )

        def __resolve_cond_value(self, c: str):
            """Resolve a condition value: try int first, fall back to variable lookup."""
            try:
                return int(c)
            except ValueError:
                # Bare identifier - resolve as variable reference
                if c.startswith("_"):
                    val = self.__ppp.system_variables.get(c, None)
                    if val is None:
                        val = ""
                        self.warn_or_stop(f"Unknown system variable {c}")
                else:
                    val = self.__get_user_variable_value(c)
                    if val is None:
                        val = ""
                        self.warn_or_stop(f"Unknown user variable {c}")
                return val.lower() if isinstance(val, str) else val

        def __eval_basiccondition(self, cond_var: str, cond_comp: str, cond_value: str | list[str]) -> bool:
            """
            Evaluate a condition based on the given variable, comparison, and value.

            Args:
                cond_var (str): The variable to be compared.
                cond_comp (str): The comparison operator.
                cond_value (str or list[str]): The value to be compared with.

            Returns:
                bool: The result of the condition evaluation.
            """
            if cond_var.lower() == "false":
                var_value = "false"
            elif cond_var.lower() == "true":
                var_value = "true"
            elif cond_var.startswith("_"):  # system variable
                var_value = self.__ppp.system_variables.get(cond_var, None)
                if var_value is None:
                    var_value = ""
                    self.warn_or_stop(f"Unknown system variable {cond_var}")
            else:  # user variable
                var_value = self.__get_user_variable_value(cond_var)
                if var_value is None:
                    var_value = ""
                    self.warn_or_stop(f"Unknown user variable {cond_var}")
            if isinstance(var_value, str):
                var_value = var_value.lower()
            if isinstance(cond_value, list):
                comp_ops = {
                    "contains": lambda x, y: y in x,
                    "in": lambda x, y: x == y,
                }
            else:
                cond_value = [cond_value]
                comp_ops = {
                    "eq": lambda x, y: x == y,
                    "ne": lambda x, y: x != y,
                    "gt": lambda x, y: x > y,
                    "lt": lambda x, y: x < y,
                    "ge": lambda x, y: x >= y,
                    "le": lambda x, y: x <= y,
                    "contains": lambda x, y: y in x,
                    "truthy": lambda x, y: bool(x),
                }
            if cond_comp not in comp_ops:
                return False
            cond_value_adjusted = list(
                (
                    c[1:-1].lower()
                    if c.startswith('"') or c.startswith("'")
                    else (
                        True
                        if c.lower() == "true"
                        else False if c.lower() == "false" or c == "" else self.__resolve_cond_value(c)
                    )
                )
                for c in cond_value
            )
            result = False
            for c in cond_value_adjusted:
                if isinstance(c, str):
                    var_value_adjusted = var_value
                elif isinstance(c, bool) and var_value != "false" and var_value != "" and var_value is not False:
                    var_value_adjusted = True
                elif isinstance(c, bool) and (var_value != "true" or var_value is False):
                    var_value_adjusted = False
                else:
                    try:
                        var_value_adjusted = int(var_value)
                    except (ValueError, TypeError):
                        self.warn_or_stop(f"Cannot convert variable value '{var_value}' to integer for comparison")
                        return False
                result = comp_ops[cond_comp](var_value_adjusted, c)
                if result:
                    break
            return result

        def __eval_condition(self, condition: lark.Tree) -> bool:
            """
            Evaluate an if condition based on the given condition tree.

            Args:
                condition (Node): The condition tree to be evaluated.

            Returns:
                bool: The result of the if condition evaluation.
            """
            # self.__ppp.logger.debug(f"__eval_condition {condition.data}")
            if condition.data == "operation_and":
                cond_result = True
                for c in condition.children:
                    cond_result = cond_result and self.__eval_condition(c)
                    if not cond_result:
                        break
            elif condition.data == "operation_or":
                cond_result = False
                for c in condition.children:
                    cond_result = cond_result or self.__eval_condition(c)
                    if cond_result:
                        break
            elif condition.data == "operation_not":
                cond_result = not self.__eval_condition(condition.children[0])
            else:  # truthy_operand / comparison_simple_value / comparison_list_value
                # we get the name of the variable
                cond_var = condition.children[0].value  # it should be a Token
                poscomp = 1
                invert = False
                if poscomp >= len(condition.children):
                    # no condition, just a variable
                    cond_comp = "truthy"
                    cond_value = "true"
                else:
                    # we get the comparison (with possible not) and the value
                    cond_comp = condition.children[poscomp].value  # it should be a Token
                    if cond_comp == "not":
                        invert = not invert
                        poscomp += 1
                        cond_comp = condition.children[poscomp].value  # it should be a Token
                    poscomp += 1
                    cond_value_node = condition.children[poscomp]
                    cond_value = (
                        list(v.value for v in cond_value_node.children)
                        if isinstance(cond_value_node, (lark.Tree, list))
                        else cond_value_node.value if isinstance(cond_value_node, lark.Token) else cond_value_node
                    )
                cond_result = self.__eval_basiccondition(cond_var, cond_comp, cond_value)
                if invert:
                    cond_result = not cond_result
            return cond_result

        def promptcomp(self, tree: lark.Tree):
            """
            Process a prompt composition construct in the tree.
            """
            start_result = self.result
            t1 = time.monotonic_ns()
            self.__visit(tree.children[0])
            and_processing = self.__ppp.host_config.get("and", "ok")
            if len(tree.children) > 1:
                and_replacements = {
                    "eol": ("replaced with EOL", "\n"),
                    "comma": ("replaced with COMMA", ", "),
                    "remove": ("removed", " "),
                }
                if tree.children[1] is not None:
                    self.result += f":{tree.children[1]}"
                for i in range(2, len(tree.children), 3):
                    if and_processing in and_replacements.keys():
                        self.result = (
                            self.result.rstrip()
                            + and_replacements[and_processing][1]
                            + self.__visit(tree.children[i + 1], False, True).lstrip()
                        )
                        if self.__ppp.debug_level == DEBUG_LEVEL.full:
                            self.__ppp.logger.debug(f"AND construct {and_replacements[and_processing][0]}")
                    elif and_processing == "error":
                        self.warn_or_stop("AND constructs are not allowed!")
                    else:  # and_processing == "ok":
                        if self.__ppp.cup_ands:
                            self.result = re.sub(r"[, ]+$", "\n" if self.__ppp.cup_ands_eol else " ", self.result)
                        if self.result[-1:].isalnum():  # add space if needed
                            self.result += " "
                        self.result += "AND"
                        added_result = self.__visit(tree.children[i + 1], False, True)
                        if self.__ppp.cup_ands:
                            added_result = re.sub(r"^[, ]+", " ", added_result)
                        if added_result[0:1].isalnum():  # add space if needed
                            added_result = " " + added_result
                        self.result += added_result
                        if tree.children[i + 2] is not None:
                            self.result += f":{tree.children[i+2]}"
            t2 = time.monotonic_ns()
            self.__debug_end("promptcomp", start_result, t2 - t1)

        def scheduled(self, tree: lark.Tree):
            """
            Process a scheduling construct in the tree and add it to the accumulated shell.
            """
            start_result = self.result
            t1 = time.monotonic_ns()
            before = tree.children[0]
            after = tree.children[-2]
            pos_str = tree.children[-1]
            pos = float(pos_str)
            if pos >= 1:
                pos = int(pos)
            scheduling_processing = self.__ppp.host_config.get("scheduling", "ok")
            if scheduling_processing == "before":
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Scheduling construct removed, taking before option")
                if before is not None:
                    self.__visit(before)
            elif scheduling_processing == "after":
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Scheduling construct removed, taking after option")
                if after is not None:
                    self.__visit(after)
            elif scheduling_processing == "first":
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Scheduling construct removed, taking first option")
                if before is not None:
                    self.__visit(before)
                elif after is not None:
                    self.__visit(after)
            elif scheduling_processing == "remove":
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Scheduling construct removed")
            elif scheduling_processing == "error":
                self.warn_or_stop("Scheduling constructs are not allowed!")
            else:  # scheduling_processing == "ok"
                # self.__shell.append(self.AccumulatedShell("sc", pos))
                self.result += "["
                if before is not None:
                    if self.__ppp.debug_level == DEBUG_LEVEL.full:
                        self.__ppp.logger.debug(f"Shell scheduled before with position {pos}")
                    self.__shell.append(self.AccumulatedShell("scb", pos))
                    self.__visit(before)
                    self.__shell.pop()
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug(f"Shell scheduled after with position {pos}")
                self.__shell.append(self.AccumulatedShell("sca", pos))
                self.result += ":"
                self.__visit(after)
                self.__shell.pop()
                if self.__ppp.cup_emptyconstructs and re.fullmatch(re.escape(start_result) + r"\[:\s*", self.result):
                    self.result = start_result
                else:
                    self.result += f":{pos_str}]"
                # self.__shell.pop()
            t2 = time.monotonic_ns()
            self.__debug_end("scheduled", start_result, t2 - t1, pos_str)

        def alternate(self, tree: lark.Tree):
            """
            Process an alternation construct in the tree and add it to the accumulated shell.
            """
            start_result = self.result
            t1 = time.monotonic_ns()
            alternation_processing = self.__ppp.host_config.get("alternation", "ok")
            if alternation_processing == "first":
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Alternation construct removed, taking first option")
                self.__visit(tree.children[0])
            elif alternation_processing == "remove":
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Alternation construct removed")
            elif alternation_processing == "error":
                self.warn_or_stop("Alternation constructs are not allowed!")
            else:  # alternation_processing == "ok"
                # self.__shell.append(self.AccumulatedShell("al", len(tree.children)))
                self.result += "["
                for i, opt in enumerate(tree.children):
                    if self.__ppp.debug_level == DEBUG_LEVEL.full:
                        self.__ppp.logger.debug(f"Shell alternate option {i+1}")
                    self.__shell.append(self.AccumulatedShell("alo", {"pos": i + 1, "len": len(tree.children)}))
                    if i > 0:
                        self.result += "|"
                    self.__visit(opt)
                    self.__shell.pop()
                self.result += "]"
                if self.__ppp.cup_emptyconstructs and re.fullmatch(re.escape(start_result) + r"\[\s*\]", self.result):
                    self.result = start_result
                # self.__shell.pop()
            t2 = time.monotonic_ns()
            self.__debug_end("alternate", start_result, t2 - t1)

        def attention(self, tree: lark.Tree):
            """
            Process a attention change construct in the tree and add it to the accumulated shell.
            """
            start_result = self.result
            t1 = time.monotonic_ns()
            # weight_kind: -1: remove, 0=none, 1=decrease, 2=increase, 3=specific
            if len(tree.children) == 2:
                weight_str = tree.children[-1]
                if weight_str is not None:
                    weight_kind = 3  # specific weight
                    weight = float(weight_str)
                else:
                    weight_kind = 2  # increase attention
                    weight = 1.1
                    weight_str = "1.1"
            else:
                weight_kind = 1  # decrease attention
                weight = 0.9
                weight_str = "0.9"
            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                self.__ppp.logger.debug(f"Shell attention with weight {weight}")
            current_tree = tree.children[0]
            if self.__ppp.cup_mergeattention:
                while isinstance(current_tree, lark.Tree) and current_tree.data == "attention":
                    # we merge the weights
                    if len(current_tree.children) == 2:
                        inner_weight = current_tree.children[-1]
                        if inner_weight is not None:
                            inner_weight = float(inner_weight)
                        else:
                            inner_weight = 1.1
                    else:
                        inner_weight = 0.9
                    weight *= inner_weight
                    current_tree = current_tree.children[0]
                weight = math.floor(weight * 100) / 100  # we round to 2 decimals
                weight_str = f"{weight:.2f}".rstrip("0").rstrip(".")
                if weight_str == "0.9":
                    weight_kind = 1
                elif weight_str == "1.1":
                    weight_kind = 2
                else:
                    weight_kind = 3
            attention_processing = self.__ppp.host_config.get("attention", "ok")
            if attention_processing == "parentheses":
                if weight_kind == 1:
                    weight_kind = 3
                    weight_str = "0.9"
                    if self.__ppp.debug_level == DEBUG_LEVEL.full:
                        self.__ppp.logger.debug("Converted to parentheses format")
            elif attention_processing == "disable":
                weight_kind = 0
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Attention construct disabled")
            elif attention_processing == "remove":
                weight_kind = -1
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Attention construct removed")
            elif attention_processing == "error":
                self.warn_or_stop("Attention constructs are not allowed!")
            # else: attention_processing == "ok":
            if weight_kind == -1:
                # we just ignore the attention construct
                pass
            elif weight_kind == 0:
                # we just visit the content without adding any attention
                self.__visit(current_tree)
            else:
                self.__shell.append(self.AccumulatedShell("at", (weight_kind, weight_str)))
                if weight_kind == 1:
                    starttag = "["
                    self.result += starttag
                    self.__visit(current_tree)
                    endtag = "]"
                elif weight_kind == 2:
                    starttag = "("
                    self.result += starttag
                    self.__visit(current_tree)
                    endtag = ")"
                else:  # weight_kind == 3
                    starttag = "("
                    self.result += starttag
                    self.__visit(current_tree)
                    endtag = f":{weight_str})"
                if self.__ppp.cup_emptyconstructs and re.fullmatch(
                    re.escape(start_result + starttag) + r"\s*", self.result
                ):
                    self.result = start_result
                else:
                    self.result += endtag
                self.__shell.pop()
            t2 = time.monotonic_ns()
            self.__debug_end("attention", start_result, t2 - t1, weight_str)

        def commandstn(self, tree: lark.Tree):
            """
            Process a send to negative command in the tree and add it to the list of negative tags.
            """
            start_result = self.result
            info = None
            t1 = time.monotonic_ns()
            if not self.__is_negative:
                negtagparameters = tree.children[0]
                if negtagparameters is not None:
                    parameters = negtagparameters.value  # should be a token
                else:
                    parameters = ""
                content = self.__visit(tree.children[1::], False, True)
                self.__negtags.append(
                    self.NegTag(len(self.result), len(self.result), content, parameters, self.__shell.copy())
                )
                info = f"with {parameters or 'no parameters'} : {content}"
            else:
                self.warn_or_stop("Ignored negative command in negative prompt")
                self.__visit(tree.children[1::])
            t2 = time.monotonic_ns()
            self.__debug_end("commandstn", start_result, t2 - t1, info)

        def commandstni(self, tree: lark.Tree):
            """
            Process a send to negative insertion point command in the tree and add it to the list of negative tags.
            """
            start_result = self.result
            info = None
            t1 = time.monotonic_ns()
            if self.__is_negative:
                negtagparameters = tree.children[0]
                if negtagparameters is not None:
                    parameters = negtagparameters.value  # should be a token
                else:
                    parameters = ""
                self.__negtags.append(
                    self.NegTag(len(self.result), len(self.result), "", parameters, self.__shell.copy())
                )
                info = f"with {parameters or 'no parameters'}"
            else:
                self.warn_or_stop("Ignored negative insertion point command in positive prompt")
            t2 = time.monotonic_ns()
            self.__debug_end("commandstni", start_result, t2 - t1, info)

        def __varset(
            self,
            command: str,
            variable: str,
            modifiers: lark.Tree | None,
            content: lark.Tree | None,
        ):
            """
            Process a generic set command in the tree.
            """
            t1 = time.monotonic_ns()
            start_result = self.result
            if variable.startswith("_"):
                self.warn_or_stop(f"Invalid variable name '{variable}' detected! System variables cannot be set.")
                return
            info = variable
            value_description = self.__get_original_node_content(content, None)
            value = content
            modifiers_str: list[str] = [m.value for m in modifiers.children] if modifiers is not None else []
            if any(item in modifiers_str for item in ["+", "add"]):
                info += f" += '{value_description}'"
                raw_oldvalue = self.__ppp.user_variables.get(variable, None)
                if raw_oldvalue is None:
                    newvalue = value
                    self.warn_or_stop(f"Unknown variable {variable}")
                elif isinstance(raw_oldvalue, str):
                    newvalue = lark.Tree(
                        lark.Token("RULE", "varvalue"),
                        [lark.Token("plain", raw_oldvalue), value],
                        # Meta should be {"content": raw_oldvalue + value},
                    )
                else:
                    newvalue = lark.Tree(
                        lark.Token("RULE", "varvalue"),
                        [raw_oldvalue, value],
                        # Meta should be {"content": raw_oldvalue.meta.content + value.meta.content},
                    )
            elif any(item in modifiers_str for item in ["?", "ifundefined"]):
                info += f" ?= '{value_description}'"
                raw_oldvalue = self.__ppp.user_variables.get(variable, None)
                if raw_oldvalue is None:
                    newvalue = value
                else:
                    info += " (not set)"
                    newvalue = None
            else:
                newvalue = value
            if newvalue is not None:
                if any(item in modifiers_str for item in ["!", "evaluate"]):
                    newvalue = self.__visit(newvalue, False, True)
                    info += " =! "
                else:
                    info += " = "
                self.__set_user_variable_value(variable, newvalue)
                currentvalue = self.__get_user_variable_value(variable, False)
                if currentvalue is None:
                    info += "not evaluated yet"
                else:
                    info += f"'{currentvalue}'"
            t2 = time.monotonic_ns()
            self.__debug_end(command, start_result, t2 - t1, info)

        def variableset(self, tree: lark.Tree):
            """
            Process a DP set variable command in the tree and add it to the dictionary of variables.
            """
            modifiers = tree.children[1] or lark.Tree(lark.Token("RULE", "variablesetmodifiers"), [])
            immediate = tree.children[2]
            if immediate is not None:
                modifiers.children = modifiers.children.copy()
                modifiers.children.append(immediate)
            self.__varset("variableset", str(tree.children[0]), modifiers, tree.children[3])

        def commandset(self, tree: lark.Tree):
            """
            Process a set command in the tree and add it to the dictionary of variables.
            """
            self.__varset("commandset", str(tree.children[0]), tree.children[1], tree.children[2])

        def __varecho(self, command: str, variable: str, default: lark.Tree | None):
            """
            Process a generic echo command in the tree.
            """
            t1 = time.monotonic_ns()
            start_result = self.result
            if default is not None:
                default_value = self.__visit(default, True)  # for log
            value = self.__get_user_variable_value(variable, True, True)
            if value is None:
                if default is not None:
                    v = self.__visit(default, False, True)
                    self.__ppp.echoed_variables[variable] = v
                    self.result += v
                else:
                    self.warn_or_stop(f"Unknown variable {variable}")
            else:
                self.__ppp.echoed_variables[variable] = value
            t2 = time.monotonic_ns()
            info = variable
            if default is not None:
                info += f" with default '{default_value}'"
            self.__debug_end(command, start_result, t2 - t1, info)

        def variableuse(self, tree: lark.Tree):
            """
            Process a DP use variable command in the tree.
            """
            self.__varecho("variableuse", str(tree.children[0]), tree.children[1] if len(tree.children) > 1 else None)

        def commandecho(self, tree: lark.Tree):
            """
            Process an echo command in the tree.
            """
            self.__varecho("commandecho", str(tree.children[0]), tree.children[1] if len(tree.children) > 1 else None)

        def commandif(self, tree: lark.Tree):
            """
            Process an if command in the tree.
            """
            t1 = time.monotonic_ns()
            start_result = self.result
            for i, n in enumerate(tree.children):
                content = n.children[-1]
                if len(n.children) == 2:  # its not an else
                    # has a condition
                    condition = n.children[0]
                    c = self.__get_original_node_content(condition, f"condition {i}")
                    if self.__eval_condition(condition):
                        self.__visit(content)
                        t2 = time.monotonic_ns()
                        self.__debug_end("commandif", start_result, t2 - t1, c)
                        return
                else:  # its an else
                    self.__visit(content)
                    t2 = time.monotonic_ns()
                    self.__debug_end("commandif", start_result, t2 - t1, "else")
                    return

        def commandext(self, tree: lark.Tree):
            """
            Process an extranetwork command in the tree.
            """
            t1 = time.monotonic_ns()
            start_result = self.result
            extnet = "(ignored)"
            if not self.__ppp.rem_removeextranetworktags:
                extnet_type: str = (tree.children[0].children[0] or "") + tree.children[0].children[1]
                is_mapping = extnet_type.startswith("$")
                if is_mapping:
                    extnet_type = extnet_type[1:]
                extnet_id: str = tree.children[1].value
                if extnet_id.startswith("'") or extnet_id.startswith('"'):
                    extnet_id = extnet_id[1:-1]
                extnet_id = re.sub(r"\\(.)", r"\1", extnet_id)  # so we can escape some special characters
                parameters: str = ""
                parameters_defaulted = False
                if tree.children[2]:
                    parameters = tree.children[2].value
                elif extnet_type in ("lora", "hypernet"):
                    parameters = "1"
                    parameters_defaulted = True
                if parameters.startswith("'") or parameters.startswith('"'):
                    parameters = parameters[1:-1]
                parameters_is_number = bool(re.match(r"^[-+]?\d*\.?\d+$", parameters or ""))
                condition = tree.children[3]
                if not condition or self.__eval_condition(condition):
                    extnet_id = f"{extnet_type}:{extnet_id}"
                    triggers = tree.children[4] if len(tree.children) > 4 else None
                    extra_triggers = None
                    compiled_extra_triggers = None
                    if is_mapping:
                        found = self.__ppp.extranetwork_mappings_obj.cached_mappings.get(extnet_id, None)
                        # we assume the conditions do not change inside the prompt
                        found_in_cache = found is not None
                        if found is None:
                            found_mappings: list[PPPENMappingVariant] = []
                            else_mapping = None
                            if self.__ppp.extranetwork_mappings_obj:
                                enmapping = self.__ppp.extranetwork_mappings_obj.extranetwork_mappings.get(
                                    extnet_id, None
                                )
                                if enmapping:
                                    for v in enmapping.variants:
                                        if v.condition:
                                            try:
                                                cnd = self.__ppp.parse_prompt(
                                                    "condition", v.condition, self.__ppp.parser_condition, True
                                                )
                                            except lark.exceptions.UnexpectedInput as e:
                                                self.warn_or_stop(
                                                    f"Error parsing condition '{v.condition}' in extranetwork mapping '{extnet_id}'! : {e.__class__.__name__}",
                                                    e,
                                                )
                                                cnd = None
                                        else:
                                            cnd = "True"
                                        if cnd is not None and (cnd == "True" or self.__eval_condition(cnd)):
                                            if v.condition:
                                                found_mappings.append(v)
                                            else:
                                                else_mapping = v
                            if found_mappings:
                                found = found_mappings[
                                    self.__ppp.rng.choice(
                                        len(found_mappings),
                                        p=[v.weight or 1 for v in found_mappings],
                                    )
                                ]
                            else:
                                found = else_mapping
                            self.__ppp.extranetwork_mappings_obj.cached_mappings[extnet_id] = found
                        if found:
                            if found.name:
                                if not found_in_cache and self.__ppp.debug_level != DEBUG_LEVEL.none:
                                    self.__ppp.logger.info(
                                        f"Mapping extranetwork '{extnet_id}' to '{extnet_type}:{found.name}'"
                                    )
                                extnet_id = f"{extnet_type}:{found.name}"
                                f_parameters = found.parameters
                                if not f_parameters and extnet_type in ("lora", "hypernet"):
                                    f_parameters = "1"
                                    found_parameters_is_number = True
                                else:
                                    found_parameters_is_number = f_parameters and bool(
                                        re.match(r"^[-+]?\d*\.?\d+$", str(f_parameters) or "")
                                    )
                                if found_parameters_is_number and parameters_is_number:
                                    parameters = f"{float(f_parameters) * float(parameters):.2f}".rstrip("0").rstrip(
                                        "."
                                    )
                                elif f_parameters is not None and parameters_defaulted:
                                    parameters = f_parameters
                            elif found.triggers:
                                if not found_in_cache and self.__ppp.debug_level != DEBUG_LEVEL.none:
                                    self.__ppp.logger.info(f"Mapping extranetwork '{extnet_id}' to just triggers")
                                extnet_id = None
                            else:
                                if not found_in_cache and self.__ppp.debug_level != DEBUG_LEVEL.none:
                                    self.__ppp.logger.info(f"Mapping extranetwork '{extnet_id}' to nothing")
                                extnet_id = None
                            if found.triggers:
                                extra_triggers = ", ".join(found.triggers)
                                try:
                                    compiled_extra_triggers = self.__ppp.parse_prompt(
                                        "triggers", extra_triggers, self.__ppp.parser_content, True
                                    )
                                except lark.exceptions.UnexpectedInput as e:
                                    self.warn_or_stop(
                                        f"Error parsing triggers '{extra_triggers}' in extranetwork mapping '{extnet_id}'! : {e.__class__.__name__}",
                                        e,
                                    )
                                    compiled_extra_triggers = None
                        else:
                            self.warn_or_stop(f"Extranetwork mapping '{extnet_id}' not found!")
                    if extnet_id:
                        extnet = f"<{extnet_id}:{parameters}>"
                        self.result += extnet
                    elif triggers or compiled_extra_triggers:
                        extnet = "(only triggers)"
                    if triggers or compiled_extra_triggers:
                        if extnet_id:
                            if not self.__ppp.cup_extranetworktags:
                                self.result += " "
                        else:
                            self.result += ", "
                    if triggers:
                        self.result += self.__visit(triggers, True, True)
                    if compiled_extra_triggers:
                        if triggers:
                            self.result += ", "
                        self.result += self.__visit(compiled_extra_triggers, True, True)
                    if triggers or compiled_extra_triggers:
                        self.result += ", "
            t2 = time.monotonic_ns()
            self.__debug_end("commandext", start_result, t2 - t1, extnet)

        def commandsetwcdeffilter(self, tree: lark.Tree):
            """
            Process a setwcdeffilter (Set Wildcard Default Filter) command in the tree.
            """
            t1 = time.monotonic_ns()
            start_result = self.result
            wildcard_key: str = self.__visit(tree.children[0].children[1], False, True)
            selected_wildcards = [x.key for x in self.__ppp.wildcard_obj.get_wildcards(wildcard_key)]
            if not selected_wildcards:
                self.warn_or_stop(f"Wildcard '{wildcard_key}' not found for default filter setting!")
            else:
                filter_object = tree.children[1].children[1] if tree.children[1] is not None else None
                if filter_object is None:
                    for wc in selected_wildcards:
                        if self.__ppp.debug_level == DEBUG_LEVEL.full:
                            self.__ppp.logger.debug(f"Removed default filter for wildcard '{wc}'")
                        self.__ppp.wildcard_obj.set_wildcard_default_filter(wc, None)
                else:
                    filter_specifier: list[list[str]] = [
                        [str(label) for label in option.children] for option in filter_object.children
                    ]
                    for wc in selected_wildcards:
                        if self.__ppp.debug_level == DEBUG_LEVEL.full:
                            self.__ppp.logger.debug(f"Set default filter for wildcard '{wc}'")
                        self.__ppp.wildcard_obj.set_wildcard_default_filter(wc, filter_specifier)
            t2 = time.monotonic_ns()
            self.__debug_end("commandsetwcdeffilter", start_result, t2 - t1)

        def extranetworktag(self, tree: lark.Tree):
            """
            Process an extra network construct in the tree.
            """
            t1 = time.monotonic_ns()
            start_result = self.result
            if not self.__ppp.rem_removeextranetworktags:
                self.result += f"<{tree.children[0]}"
                self.__visit(tree.children[1])
                self.result += ">"
            t2 = time.monotonic_ns()
            self.__debug_end("extranetworktag", start_result, t2 - t1)

        def __get_choices_internal_get(
            self,
            choice_values: list[dict],
            filter_specifier: Optional[list[list[str]]] = None,
            wildcard_key: str = None,
        ) -> list[dict]:
            msg_where = f"wildcard '{wildcard_key}'" if wildcard_key else "choices"
            if filter_specifier is not None:
                filtered_choice_values = []
                for i, c in enumerate(choice_values):
                    passes = False
                    for o in filter_specifier:
                        tmp_pass = True
                        for a in o:
                            if a.isdecimal():
                                if int(a) != i:
                                    tmp_pass = False
                                    break
                            elif a.lower() not in c.get("labels", []):
                                tmp_pass = False
                                break
                        if tmp_pass:
                            passes = True
                            break
                    if passes:
                        filtered_choice_values.append(c)
                if not filtered_choice_values:
                    self.warn_or_stop(
                        f"Wildcard filter specifier '{','.join(['+'.join(y for y in x) for x in filter_specifier])}' found no matches in choices for wildcard '{wildcard_key}'!"
                    )
            else:
                filtered_choice_values = choice_values.copy()
            expanded_choice_values = []
            for i, c in enumerate(filtered_choice_values):
                if c.get("command", False):
                    content_text = self.__visit(c.get("content", ""), False, True).strip()
                    (cmd, cmd_args) = content_text.split()
                    if cmd == "include":
                        wcs = self.__ppp.wildcard_obj.get_wildcards(cmd_args)
                        if not wcs:
                            self.warn_or_stop(f"Not found included wildcard '{cmd_args}' at {msg_where}!")
                        c_weight = float(c.get("weight", 1.0))
                        for wc in wcs:
                            if wc.key in self.__seen_wildcards:
                                self.warn_or_stop(
                                    f"Circular reference detected including wildcard '{wc.key}' at {msg_where} (chain starts at '{self.__seen_wildcards[0]}')!"
                                )
                                continue
                            self.__seen_wildcards.append(wc.key)
                            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                                self.__ppp.logger.debug(f"Seen wildcard '{wc.key}'")
                                self.__ppp.logger.debug(f"Including choices from wildcard '{wc.key}'")
                            (_, choice_values) = self.__check_wildcard_initialization(wc)
                            if choice_values is not None:
                                ch_values = self.__get_choices_internal_get(choice_values, None, wc.key)
                                for cv in ch_values:
                                    expanded_choice_values.append(
                                        {
                                            **cv,
                                            "weight": float(cv.get("weight", 1.0) * c_weight),  # we adjust the weight
                                        }
                                    )
                    else:
                        self.warn_or_stop(f"Unsupported choice command '{cmd}' at {msg_where}!")
                else:
                    expanded_choice_values.append(c)
            return expanded_choice_values

        def __get_choices_internal_select(
            self,
            options: dict | None,
            choice_values: list[dict],
            filter_specifier: Optional[list[list[str]]] = None,
            wildcard_key: str = None,
        ) -> tuple[str, list[str], str, str]:
            """
            Select choices based on the options.

            Args:
                options (dict): The object representing the options construct.
                choice_values (list[dict]): A list of choice objects.
                filter_specifier (list[list[str]]): The filter specifier.
                wildcard_key (str): The wildcard key if it is a wildcard.

            Returns:
                tuple: A tuple containing the prefix, selected choices, separator and suffix
            """
            seen_wildcards_len = len(self.__seen_wildcards)
            if options is None:
                options = {}
            sampler: str = options.get("sampler", "~")
            repeating: bool = options.get("repeating", False)
            optional: bool = options.get("optional", False)
            if "count" in options:
                from_value = options["count"]
                to_value = from_value
            else:
                from_value: int = options.get("from", 1)
                to_value: int = options.get("to", 1)
            separator: str = options.get("separator", self.__ppp.wil_choice_separator)
            msg_where = f"wildcard '{wildcard_key}'" if wildcard_key else "choices"
            if sampler != "~":
                self.warn_or_stop(f"Unsupported sampler '{sampler}' at {msg_where} options!")
                sampler = "~"
            expanded_choice_values = self.__get_choices_internal_get(choice_values, filter_specifier, wildcard_key)
            available_choices: list[dict] = []
            weights = []
            included_choices = 0
            excluded_choices = 0
            excluded_weights_sum = 0
            for i, c in enumerate(expanded_choice_values):
                c["choice_index"] = i  # we index them to later sort the results
                weight = float(c.get("weight", 1.0))
                condition = c.get("if", None)
                if weight > 0 and (condition is None or self.__eval_condition(condition)):
                    available_choices.append(c)
                    weights.append(weight)
                    included_choices += 1
                else:
                    weights.append(-1)
                    excluded_choices += 1
                    excluded_weights_sum += weight
            if excluded_choices > 0:  # we need to redistribute the excluded weights
                weights = [weight + excluded_weights_sum / included_choices for weight in weights if weight >= 0]
            weights = np.array(weights)
            weights /= weights.sum()  # normalize weights
            if available_choices:
                if from_value < 0:
                    from_value = 1
                elif from_value > len(available_choices):
                    from_value = len(available_choices)
                if to_value < 1:
                    to_value = 1
                elif (to_value > len(available_choices) and not repeating) or from_value > to_value:
                    to_value = len(available_choices)
                num_choices = (
                    self.__ppp.rng.integers(from_value, to_value, endpoint=True)
                    if from_value < to_value
                    else from_value
                )
            else:
                num_choices = 0
                if not optional and from_value > 0:
                    self.warn_or_stop(f"Not enough choices found for {msg_where}!")
            if num_choices < 2:
                repeating = False
            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                self.__ppp.logger.debug(
                    self.__ppp.format_output(
                        f"Selecting {'optional ' if optional else ''}{'repeating ' if repeating else ''}{num_choices} choice"
                        + ("s" if num_choices != 1 else "")
                        + (f" and separating with '{separator}'" if num_choices > 1 else "")
                    )
                )
            if num_choices > 0:
                selected_choices: list[dict] = (
                    list(self.__ppp.rng.choice(available_choices, size=num_choices, p=weights, replace=repeating))
                    if available_choices
                    else []
                )
                if self.__ppp.wil_keep_choices_order:
                    selected_choices = sorted(selected_choices, key=lambda x: x["choice_index"])
                selected_choices_text = []
                prefix: str = (
                    self.__visit(options.get("prefix", None), False, True)
                    if options.get("prefix", None) is not None
                    else ""
                )
                if prefix != "" and re.match(r"\w", prefix[-1]):
                    prefix += " "
                for i, c in enumerate(selected_choices):
                    t1 = time.monotonic_ns()
                    choice_content_obj = c.get("content", c.get("text", None))
                    if isinstance(choice_content_obj, str):
                        choice_content = choice_content_obj
                    else:
                        choice_content = self.__visit(choice_content_obj, False, True)
                    t2 = time.monotonic_ns()
                    if self.__ppp.debug_level == DEBUG_LEVEL.full:
                        self.__ppp.logger.debug(
                            f"Adding choice {i+1} ({(t2-t1) / 1_000_000_000:.3f} seconds):\n"
                            + textwrap.indent(re.sub(r"\n$", "", choice_content), "    ")
                        )
                    selected_choices_text.append(choice_content)
                suffix: str = (
                    self.__visit(options.get("suffix", None), False, True)
                    if options.get("suffix", None) is not None
                    else ""
                )
                if suffix != "" and re.match(r"\w", suffix[0]):
                    suffix = " " + suffix
                # remove comments
                results = [re.sub(r"\s*#[^\n]*(?:\n|$)", "", r, flags=re.DOTALL) for r in selected_choices_text]
            else:
                prefix = ""
                suffix = ""
                results = []
            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                list_unseen = [f"'{x}'" for x in self.__seen_wildcards[seen_wildcards_len:]]
                self.__ppp.logger.debug(f"Unseen wildcards: {', '.join(list_unseen)}")
            self.__seen_wildcards = self.__seen_wildcards[:seen_wildcards_len]
            return (prefix, results, separator, suffix)

        def __get_choices(
            self,
            options: dict | None,
            choice_values: list[dict],
            filter_specifier: Optional[list[list[str]]] = None,
            wildcard_key: str = None,
        ) -> str:
            r = self.__get_choices_internal_select(options, choice_values, filter_specifier, wildcard_key)
            if r[1]:
                return r[0] + r[2].join(r[1]) + r[3]
            return ""

        def __convert_choices_options(self, options: Optional[lark.Tree]) -> dict:
            """
            Convert the choices options to a dictionary.

            Args:
                options (Tree): The choices options tree.

            Returns:
                dict: The converted choices options.
            """
            if options is None:
                return None
            options_dict = {}
            if len(options.children) == 1:
                options_dict["sampler"] = options.children[0] if options.children[0] is not None else "~"
            else:
                options_dict["sampler"] = options.children[0].children[0] if options.children[0] is not None else "~"
                options_dict["repeating"] = (
                    "r" in options.children[1].children[0] if options.children[1] is not None else False
                )
                options_dict["optional"] = (
                    "o" in options.children[1].children[0] if options.children[1] is not None else False
                )
                if len(options.children) == 4:
                    ifrom = 2
                    ito = 2
                    isep = 3
                else:  # 6
                    ifrom = 2
                    ito = 3
                    isep = 4
                options_dict["from"] = (
                    int(options.children[ifrom].children[0]) if options.children[ifrom] is not None else 1
                )
                options_dict["to"] = int(options.children[ito].children[0]) if options.children[ito] is not None else 1
                options_dict["separator"] = (
                    self.__visit(options.children[isep], False, True)
                    if options.children[isep] is not None
                    else self.__ppp.wil_choice_separator
                )
            return options_dict

        def __convert_choice(self, choice: lark.Tree) -> dict:
            """
            Convert the choice to a dictionary.

            Args:
                choice (Tree): The choice tree.

            Returns:
                dict: The converted choice.
            """
            choice_dict = {}
            choice_dict["command"] = choice.children[0] is not None
            c_label_obj = choice.children[1]
            choice_dict["labels"] = (
                [x.value.lower() for x in c_label_obj.children[1:-1]]  # should be a token
                if c_label_obj is not None
                else []
            )
            choice_dict["weight"] = float(choice.children[2].children[0]) if choice.children[2] is not None else 1.0
            choice_dict["if"] = choice.children[3].children[0] if choice.children[3] is not None else None
            choice_dict["content"] = choice.children[-1]
            return choice_dict

        def __check_wildcard_initialization(self, wildcard: PPPWildcard) -> tuple[dict | None, list[dict] | None]:
            """
            Initializes a wildcard if it hasn't been yet.

            Args:
                wildcard (PPPWildcard): The wildcard to check.
            Returns:
                tuple: A tuple containing the options and choice values of the wildcard.
            """
            choice_values = wildcard.choices
            options = wildcard.options
            if choice_values is None:
                t1 = time.monotonic_ns()
                choice_values = []
                n = 0
                # we check the first choice to see if it is actually options
                if isinstance(wildcard.unprocessed_choices[0], dict):
                    if self.__ppp.wildcard_obj.is_dict_choices_options(wildcard.unprocessed_choices[0]):
                        options = wildcard.unprocessed_choices[0]
                        prefix = options.get("prefix", None)
                        if prefix is not None and isinstance(prefix, str):
                            try:
                                options["prefix"] = self.__ppp.parse_prompt(
                                    "choicevalue", prefix, self.__ppp.parser_choicevalue, True
                                )
                            except lark.exceptions.UnexpectedInput as e:
                                self.warn_or_stop(
                                    f"Error parsing choice prefix '{prefix}' in wildcard '{wildcard.key}'! : {e.__class__.__name__}",
                                    e,
                                )
                        suffix = options.get("suffix", None)
                        if suffix is not None and isinstance(suffix, str):
                            try:
                                options["suffix"] = self.__ppp.parse_prompt(
                                    "choicevalue", suffix, self.__ppp.parser_choicevalue, True
                                )
                            except lark.exceptions.UnexpectedInput as e:
                                self.warn_or_stop(
                                    f"Error parsing choice suffix '{suffix}' in wildcard '{wildcard.key}'! : {e.__class__.__name__}",
                                    e,
                                )
                        n = 1
                else:
                    if wildcard.unprocessed_choices[0].endswith("$$"):
                        try:
                            options = self.__convert_choices_options(
                                self.__ppp.parse_prompt(
                                    "as choices options",
                                    wildcard.unprocessed_choices[0][:-2].strip(),
                                    self.__ppp.parser_choicesoptions,
                                    True,
                                )
                            )
                            n = 1
                        except lark.exceptions.UnexpectedInput:
                            options = None
                if options is None and self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Does not have options")
                wildcard.options = options
                # we process the choices
                for cv in wildcard.unprocessed_choices[n:]:
                    if isinstance(cv, dict):
                        if self.__ppp.wildcard_obj.is_dict_choice_options(cv):
                            condition = cv.get("if", None)
                            if condition is not None and isinstance(condition, str):
                                try:
                                    cv["if"] = self.__ppp.parse_prompt(
                                        "condition", condition, self.__ppp.parser_condition, True
                                    )
                                except lark.exceptions.UnexpectedInput as e:
                                    self.warn_or_stop(
                                        f"Error parsing condition '{condition}' in wildcard '{wildcard.key}'! : {e.__class__.__name__}",
                                        e,
                                    )
                                    cv["if"] = None
                            content = cv.get("content", cv.get("text", None))
                            cv["content"] = content
                            if "text" in cv:
                                del cv["text"]
                            if content is not None and isinstance(content, str):
                                try:
                                    cv["content"] = self.__ppp.parse_prompt(
                                        "choicevalue", content, self.__ppp.parser_choicevalue, True
                                    )
                                except lark.exceptions.UnexpectedInput as e:
                                    self.warn_or_stop(
                                        f"Error parsing choice content '{content}' in wildcard '{wildcard.key}'! : {e.__class__.__name__}",
                                        e,
                                    )
                                    cv["content"] = None
                            if cv["content"] is not None:
                                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                                    self.__ppp.logger.debug(f"Processed choice {cv}")
                                choice_values.append(cv)
                            else:
                                self.warn_or_stop(f"Invalid choice {cv} in wildcard '{wildcard.key}'!")
                        else:
                            self.warn_or_stop(f"Invalid choice {cv} in wildcard '{wildcard.key}'!")
                    else:
                        try:
                            choice_values.append(
                                self.__convert_choice(
                                    self.__ppp.parse_prompt("choice", cv, self.__ppp.parser_choice, True)
                                )
                            )
                        except lark.exceptions.UnexpectedInput as e:
                            self.warn_or_stop(
                                f"Error parsing choice '{cv}' in wildcard '{wildcard.key}'! : {e.__class__.__name__}", e
                            )
                wildcard.choices = choice_values
                t2 = time.monotonic_ns()
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug(
                        f"Processed choices for wildcard '{wildcard.key}' ({(t2-t1) / 1_000_000_000:.3f} seconds)"
                    )
            return (options, choice_values)

        def wildcard(self, tree: lark.Tree):
            """
            Process a wildcard construct in the tree.
            """
            t1 = time.monotonic_ns()
            seen_wildcards_len = len(self.__seen_wildcards)
            start_result = self.result
            applied_options = self.__convert_choices_options(tree.children[0])
            wildcard_key: str = self.__visit(tree.children[1], False, True)
            wc = self.__get_original_node_content(tree, f"?__{wildcard_key}__")
            if self.__ppp.wil_process_wildcards:
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug(f"Processing wildcard: {wildcard_key}")
                selected_wildcards = self.__ppp.wildcard_obj.get_wildcards(wildcard_key)
                if not selected_wildcards:
                    self.detectedWildcards.append(wc)
                    self.result += wc
                    t2 = time.monotonic_ns()
                    self.__debug_end("wildcard", start_result, t2 - t1, wc)
                    return
                filter_specifier: list[int | str] = None
                filter_object = tree.children[2]
                if filter_object is not None:
                    if (
                        isinstance(filter_object.children[1], lark.Token)
                        and filter_object.children[1] is not None
                        and "^" in filter_object.children[1]
                    ):
                        filter_wildcard_key = self.__visit(filter_object.children[2], False, True)
                        filter_specifier = self.__wildcard_filters.get(filter_wildcard_key, None)
                        if self.__ppp.debug_level == DEBUG_LEVEL.full:
                            self.__ppp.logger.debug("Filtering choices with inherited filter")
                    else:
                        filter_specifier = [[y.value for y in x.children] for x in filter_object.children[2].children]
                        if self.__ppp.debug_level == DEBUG_LEVEL.full:
                            self.__ppp.logger.debug("Filtering choices")
                    self.__wildcard_filters[wildcard_key] = filter_specifier
                    if (
                        filter_object.children[1] is not None and "#" in filter_object.children[1]
                    ):  # means do not use the filter in this wildcard
                        if self.__ppp.debug_level == DEBUG_LEVEL.full:
                            self.__ppp.logger.debug("Ignoring filter")
                        filter_specifier = None
                else:
                    filter_specifier = self.__ppp.wildcard_obj.get_wildcard_default_filter(wildcard_key)
                    if filter_specifier is not None:
                        self.__wildcard_filters[wildcard_key] = filter_specifier
                        if self.__ppp.debug_level == DEBUG_LEVEL.full:
                            self.__ppp.logger.debug("Applying default filter")
                if (
                    len(selected_wildcards) > 1
                    and filter_specifier is not None
                    and any(x.isdecimal() for x in filter_specifier)
                ):
                    self.__ppp.logger.warning(
                        f"Using a globbing wildcard '{wildcard_key}' with positional index filters is not recommended!"
                    )
                var_object = tree.children[3]
                variablename = None
                variablebackup = None
                if var_object is not None:
                    variablename = var_object.children[0]  # should be a token
                    variablevalue = self.__visit(var_object.children[1], False, True)
                    variablebackup = self.__ppp.user_variables.get(variablename, None)
                    self.__remove_user_variable(variablename)
                    self.__set_user_variable_value(variablename, variablevalue)
                choice_values_all = []
                for wildcard in selected_wildcards:
                    if wildcard is None:
                        self.detectedWildcards.append(wc)
                        self.result += wc
                        t2 = time.monotonic_ns()
                        self.__debug_end("wildcard", start_result, t2 - t1, wc)
                        return
                    if wildcard.key in self.__seen_wildcards:
                        self.warn_or_stop(
                            f"Circular reference detected with wildcard '{self.__seen_wildcards[-1]}' (chain starts at '{self.__seen_wildcards[0]}')!"
                        )
                        continue
                    self.__seen_wildcards.append(wildcard.key)
                    if self.__ppp.debug_level == DEBUG_LEVEL.full:
                        self.__ppp.logger.debug(f"Seen wildcard '{wildcard.key}'")
                    (options, choice_values) = self.__check_wildcard_initialization(wildcard)
                    if options is not None:
                        if applied_options is None:
                            applied_options = options
                        else:
                            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                                self.__ppp.logger.debug(f"Options for wildcard '{wildcard.key}' are ignored!")
                    choice_values_all += choice_values
                self.result += self.__get_choices(applied_options, choice_values_all, filter_specifier, wildcard_key)
                if wildcard_key in self.__wildcard_filters:
                    del self.__wildcard_filters[wildcard_key]
                if variablename is not None:
                    self.__remove_user_variable(variablename)
                    if variablebackup is not None:
                        self.__ppp.user_variables[variablename] = variablebackup
            elif self.__ppp.wil_ifwildcards != self.__ppp.IFWILDCARDS_CHOICES.remove:
                self.detectedWildcards.append(wc)
                self.result += wc
            if self.__ppp.debug_level == DEBUG_LEVEL.full:
                list_unseen = [f"'{x}'" for x in self.__seen_wildcards[seen_wildcards_len:]]
                self.__ppp.logger.debug(f"Unseen wildcards: {', '.join(list_unseen)}")
            self.__seen_wildcards = self.__seen_wildcards[:seen_wildcards_len]
            t2 = time.monotonic_ns()
            self.__debug_end("wildcard", start_result, t2 - t1, f"'{wc}'")

        def choices(self, tree: lark.Tree):
            """
            Process a choices construct in the tree.
            """
            t1 = time.monotonic_ns()
            start_result = self.result
            options = self.__convert_choices_options(tree.children[0])
            choice_values = [self.__convert_choice(c) for c in tree.children[1::]]
            ch = self.__get_original_node_content(tree, "?{...}")
            if self.__ppp.wil_process_wildcards:
                if self.__ppp.debug_level == DEBUG_LEVEL.full:
                    self.__ppp.logger.debug("Processing choices:")
                self.result += self.__get_choices(options, choice_values)
            elif self.__ppp.wil_ifwildcards != self.__ppp.IFWILDCARDS_CHOICES.remove:
                self.detectedWildcards.append(ch)
                self.result += ch
            t2 = time.monotonic_ns()
            self.__debug_end("choices", start_result, t2 - t1, f"'{ch}'")

        def __default__(self, tree):
            t1 = time.monotonic_ns()
            start_result = self.result
            self.__visit(tree.children)
            t2 = time.monotonic_ns()
            self.__debug_end(tree.data.value, start_result, t2 - t1)

        def start(self, tree):
            self.result = ""
            t1 = time.monotonic_ns()
            self.__visit(tree.children)
            attention_processing = self.__ppp.host_config.get("attention", "ok")
            # process the found negative tags
            for negtag in self.__negtags:
                if self.__ppp.cup_mergeattention:
                    # join consecutive attention elements
                    for i in range(len(negtag.shell) - 1, 0, -1):
                        if negtag.shell[i].type == "at" and negtag.shell[i - 1].type == "at":
                            new_weight = (  # we limit the new weight to two decimals
                                math.floor(100 * float(negtag.shell[i - 1].data[1]) * float(negtag.shell[i].data[1]))
                                / 100
                            )
                            new_weight_str = f"{new_weight:.2f}".rstrip("0").rstrip(".")
                            if new_weight_str == "0.9" and attention_processing != "parentheses":
                                new_kind = 1
                            elif new_weight_str == "1.1":
                                new_kind = 2
                            else:
                                new_kind = 3
                            negtag.shell[i - 1] = self.AccumulatedShell(
                                "at",
                                (new_kind, new_weight_str),
                            )
                            negtag.shell.pop(i)
                start = ""
                end = ""
                for s in negtag.shell:
                    match s.type:
                        case "at":
                            if s.data[0] == 1:
                                start += "["
                                end = "]" + end
                            elif s.data[0] == 2:
                                start += "("
                                end = ")" + end
                            else:  # 3
                                start += "("
                                end = f":{s.data[1]})" + end
                        # case "sc":
                        case "scb":
                            start += "["
                            end = f"::{s.data}]" + end
                        case "sca":
                            start += "["
                            end = f":{s.data}]" + end
                        # case "al":
                        case "alo":
                            start += "[" + ("|" * int(s.data["pos"] - 1))
                            end = ("|" * int(s.data["len"] - s.data["pos"])) + "]" + end
                content = start + negtag.content + end
                position = negtag.parameters or "s"
                if position.startswith("i"):
                    n = int(position[1])
                    self.insertion_at[n] = [negtag.start, negtag.end]
                elif len(content) > 0:
                    if content not in self.__already_processed:
                        if self.__ppp.stn_ignore_repeats:
                            self.__already_processed.append(content)
                        if self.__ppp.debug_level == DEBUG_LEVEL.full:
                            self.__ppp.logger.debug(
                                self.__ppp.format_output(f"Adding content at position {position}: {content}")
                            )
                        if position == "e":
                            self.add_at["end"].append(content)
                        elif position.startswith("p"):
                            n = int(position[1])
                            self.add_at["insertion_point"][n].append(content)
                        else:  # position == "s" or invalid
                            self.add_at["start"].append(content)
                    else:
                        self.__ppp.logger.warning(self.__ppp.format_output(f"Ignoring repeated content: {content}"))
            t2 = time.monotonic_ns()
            self.__debug_end("start", "", t2 - t1)
