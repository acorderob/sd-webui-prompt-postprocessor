import dataclasses
import logging
import os
import re
import time
from typing import Any, Callable, Optional
import lark
import numpy as np
import yaml

from ppp_classes import IFWILDCARDS_CHOICES, SUPPORTED_APPS, PPPInterrupt, PPPState, PPPStateOptions
from ppp_logging import DEBUG_LEVEL, log
from ppp_tree import TreeProcessor
from ppp_utils import escape_single_quotes
from ppp_common import load_grammar, parse_prompt, preprocess_grammar, warn_or_stop
from ppp_wildcards import PPPWildcards
from ppp_enmappings import PPPExtraNetworkMappings


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

    defopt = {f.name: f.default for f in dataclasses.fields(PPPStateOptions)}
    DEFAULT_DEBUG_LEVEL = defopt["debug_level"].value
    DEFAULT_ON_WARNING = defopt["on_warning"].value
    DEFAULT_STN_SEPARATOR = defopt["stn_separator"]
    DEFAULT_STN_IGNORE_REPEATS = defopt["stn_ignore_repeats"]
    DEFAULT_PROCESS_WILDCARDS = defopt["process_wildcards"]
    DEFAULT_IF_WILDCARDS = defopt["if_wildcards"].value
    DEFAULT_CHOICE_SEPARATOR = defopt["choice_separator"]
    DEFAULT_KEEP_CHOICES_ORDER = defopt["keep_choices_order"]
    DEFAULT_DO_CLEANUP = defopt["cup_do_cleanup"]
    DEFAULT_CLEANUP_VARIABLES = defopt["cup_cleanup_variables"]
    DEFAULT_CUP_EXTRA_SPACES = defopt["cup_extra_spaces"]
    DEFAULT_CUP_EMPTY_CONSTRUCTS = defopt["cup_empty_constructs"]
    DEFAULT_CUP_EXTRA_SEPARATORS = defopt["cup_extra_separators"]
    DEFAULT_CUP_EXTRA_SEPARATORS2 = defopt["cup_extra_separators2"]
    DEFAULT_CUP_EXTRA_SEPARATORS_INCLUDE_EOL = defopt["cup_extra_separators_include_eol"]
    DEFAULT_CUP_BREAKS = defopt["cup_breaks"]
    DEFAULT_CUP_BREAKS_EOL = defopt["cup_breaks_eol"]
    DEFAULT_CUP_ANDS = defopt["cup_ands"]
    DEFAULT_CUP_ANDS_EOL = defopt["cup_ands_eol"]
    DEFAULT_CUP_EXTRANETWORK_TAGS = defopt["cup_extranetwork_tags"]
    DEFAULT_CUP_MERGE_ATTENTION = defopt["cup_merge_attention"]
    DEFAULT_CUP_REMOVE_EXTRANETWORK_TAGS = defopt["cup_remove_extranetwork_tags"]
    WILDCARD_WARNING = '(WARNING TEXT "INVALID WILDCARD" IN BRIGHT RED:1.5)\nBREAK '
    WILDCARD_STOP = "INVALID WILDCARD! {0}\nBREAK "
    UNPROCESSED_STOP = "UNPROCESSED CONSTRUCTS!\nBREAK "

    def __init__(
        self,
        logger: logging.Logger,
        env_info: dict[str, Any],
        options: PPPStateOptions,
        grammar_content: Optional[str] = None,
        interrupt: Optional[Callable] = None,
        wildcards_obj: PPPWildcards = None,
        extranetwork_mappings_obj: PPPExtraNetworkMappings = None,
    ):
        """
        Initializes the PPP object.

        Args:
            logger: The logger object.
            interrupt: The interrupt function.
            env_info: A dictionary with information for the environment and loaded model.
            options: The options object for configuring PPP behavior.
            grammar_content: Optional. The grammar content to be used for parsing.
            wildcards_obj: Optional. The wildcards object to be used for processing wildcards.
            extranetwork_mappings_obj: Optional. The extranetwork mappings object to be used for processing.
        """
        self.logger = logger
        self.debug_level = options.debug_level
        self.interrupt_callback = interrupt
        self.env_info = env_info

        default_config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ppp_config.yaml.defaults")
        try:
            with open(default_config_file, "r", encoding="utf-8") as f:
                self.config: dict[str, Any] = yaml.safe_load(f)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.config = {}
            raise PPPInterrupt(
                f"Failed to load default configuration from '{escape_single_quotes(default_config_file)}'."
            ) from exc
        validate_def_cfg = self.__validate_normalize_configuration(self.config, "default configuration file")
        if validate_def_cfg != 0:
            errmsg = "Default configuration file has errors. Please restore the default configuration file and, per instructions, use a copy to adapt it."
            if validate_def_cfg == 2:
                raise PPPInterrupt(errmsg)
            self.log(logging.WARNING, errmsg)

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
                        self.log(logging.WARNING, "Failed to get user directory for PPP config.")
                if not user_config_file or not os.path.exists(user_config_file):
                    user_config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ppp_config.yaml")
            if user_config_file and os.path.exists(user_config_file):
                with open(user_config_file, "r", encoding="utf-8") as f:
                    user_config = yaml.safe_load(f)
                self.__validate_normalize_configuration(user_config, "user configuration")
        if user_config:
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

        host_config: dict[str, Any] = (self.config.get("hosts") or {}).get(self.env_info.get("app", ""))
        if host_config is None:
            raise PPPInterrupt(
                f"No host configuration found for app '{escape_single_quotes(self.env_info.get('app', ''))}'. Please check your configuration."
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
        self.variants_definitions = {}
        for m in self.known_models:
            for v, vo in (((self.models_config or {}).get(m) or {}).get("variants") or {}).items():
                if v not in self.known_models:
                    self.variants_definitions[v] = (m, vo["find_in_filename"])
                else:
                    self.log(
                        logging.WARNING,
                        f"Variant name '{escape_single_quotes(v)}' in model '{escape_single_quotes(m)}' conflicts with a known model name. Discarding variant.",
                    )
        self.log(logging.DEBUG, f"Host configuration: {host_config}", min_level=DEBUG_LEVEL.minimal)

        # self.log(logging.INFO, f"Detected environment info: {env_info}", min_level=DEBUG_LEVEL.minimal)

        if grammar_content is None:
            grammar_content = load_grammar()
        # Preprocess grammar content for conditional compilation
        grammar_content_full = preprocess_grammar(
            grammar_content,
            {
                "ALLOW_NEW_CONTENT": True,
                "ALLOW_WILDCARDS": True,
                "ALLOW_CHOICES": True,
                "ALLOW_COMMVARS": True,
            },
            self.logger,
            self.debug_level,
        )

        self.state = PPPState(
            logger=self.logger,
            host_config=host_config,
            options=options,
            system_variables={},
            user_variables={},
            echoed_variables={},
            wildcards_obj=wildcards_obj,
            extranetwork_mappings_obj=extranetwork_mappings_obj,
            parsers={
                "full": lark.Lark(
                    grammar_content_full,
                    propagate_positions=True,
                ),
                "wc_ch": lark.Lark(
                    preprocess_grammar(
                        grammar_content,
                        {
                            "ALLOW_NEW_CONTENT": True,
                            "ALLOW_WILDCARDS": True,
                            "ALLOW_CHOICES": True,
                            "ALLOW_COMMVARS": False,
                        },
                        self.logger,
                        self.debug_level,
                    ),
                    propagate_positions=True,
                ),
                "wc_cv": lark.Lark(
                    preprocess_grammar(
                        grammar_content,
                        {
                            "ALLOW_NEW_CONTENT": True,
                            "ALLOW_WILDCARDS": True,
                            "ALLOW_CHOICES": False,
                            "ALLOW_COMMVARS": True,
                        },
                        self.logger,
                        self.debug_level,
                    ),
                    propagate_positions=True,
                ),
                "ch_cv": lark.Lark(
                    preprocess_grammar(
                        grammar_content,
                        {
                            "ALLOW_NEW_CONTENT": True,
                            "ALLOW_WILDCARDS": False,
                            "ALLOW_CHOICES": True,
                            "ALLOW_COMMVARS": True,
                        },
                        self.logger,
                        self.debug_level,
                    ),
                    propagate_positions=True,
                ),
                "wc": lark.Lark(
                    preprocess_grammar(
                        grammar_content,
                        {
                            "ALLOW_NEW_CONTENT": True,
                            "ALLOW_WILDCARDS": True,
                            "ALLOW_CHOICES": False,
                            "ALLOW_COMMVARS": False,
                        },
                        self.logger,
                        self.debug_level,
                    ),
                    propagate_positions=True,
                ),
                "ch": lark.Lark(
                    preprocess_grammar(
                        grammar_content,
                        {
                            "ALLOW_NEW_CONTENT": True,
                            "ALLOW_WILDCARDS": False,
                            "ALLOW_CHOICES": True,
                            "ALLOW_COMMVARS": False,
                        },
                        self.logger,
                        self.debug_level,
                    ),
                    propagate_positions=True,
                ),
                "cv": lark.Lark(
                    preprocess_grammar(
                        grammar_content,
                        {
                            "ALLOW_NEW_CONTENT": True,
                            "ALLOW_WILDCARDS": False,
                            "ALLOW_CHOICES": False,
                            "ALLOW_COMMVARS": True,
                        },
                        self.logger,
                        self.debug_level,
                    ),
                    propagate_positions=True,
                ),
                "only_old": lark.Lark(
                    preprocess_grammar(
                        grammar_content,
                        {
                            "ALLOW_NEW_CONTENT": False,
                            "ALLOW_WILDCARDS": False,
                            "ALLOW_CHOICES": False,
                            "ALLOW_COMMVARS": False,
                        },
                        self.logger,
                        self.debug_level,
                    ),
                    propagate_positions=True,
                ),
                # Partial parsers
                "content": lark.Lark(
                    grammar_content_full,
                    propagate_positions=True,
                    start="content",
                ),
                "choice": lark.Lark(
                    grammar_content_full,
                    propagate_positions=True,
                    start="choice",
                ),
                "wcdefoptions": lark.Lark(
                    grammar_content_full,
                    propagate_positions=True,
                    start="wcdefoptions",
                ),
                "condition": lark.Lark(
                    grammar_content_full,
                    propagate_positions=True,
                    start="condition",
                ),
                "choicevalue": lark.Lark(
                    grammar_content_full,
                    propagate_positions=True,
                    start="choicevalue",
                ),
            },
        )
        self.__init_sysvars()

    def log(self, kind, message: str, min_level: DEBUG_LEVEL | None = None):
        log(self.logger, self.debug_level, kind, message, min_level)

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
                self.log(
                    logging.WARNING,
                    f"{where.title()}: Invalid regex pattern for variant '{escape_single_quotes(variant_key)}' in model '{escape_single_quotes(model_key)}'. Discarding variant.",
                )
        elif isinstance(find_in_filename, dict):
            regex = find_in_filename.get("regex", "")
            flags = find_in_filename.get("flags", [])
            if not isinstance(regex, str) or not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
                self.log(
                    logging.WARNING,
                    f"{where.title()}: Invalid format for 'find_in_filename' for variant '{escape_single_quotes(variant_key)}' in model '{escape_single_quotes(model_key)}'. Discarding variant.",
                )
            else:
                fl = self.__re_flags_from_list(flags)
                if fl == 0 and len(flags):
                    self.log(
                        logging.WARNING,
                        f"{where.title()}: Invalid regex flags for variant '{escape_single_quotes(variant_key)}' in model '{escape_single_quotes(model_key)}'. Discarding variant.",
                    )
                try:
                    re.compile(regex, fl)
                    return {"regex": regex, "flags": fl}
                except re.error:
                    self.log(
                        logging.WARNING,
                        f"{where.title()}: Invalid regex pattern for variant '{escape_single_quotes(variant_key)}' in model '{escape_single_quotes(model_key)}'. Discarding variant.",
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
            self.log(logging.ERROR, f"{where.capitalize()}: is not a dictionary.")
            fatal_errors = True
        else:
            if cfg.get("hosts") and not isinstance(cfg["hosts"], dict):
                self.log(logging.ERROR, f"{where.capitalize()}: 'hosts' is not a valid dictionary.")
                fatal_errors = True
            if cfg.get("models") and not isinstance(cfg.get("models"), dict):
                self.log(logging.ERROR, f"{where.capitalize()}: 'models' is not a valid dictionary.")
                fatal_errors = True
        if fatal_errors:
            return 2
        result = 0
        defcfg_hosts: dict[str, Any] = cfg.get("hosts", {})
        for host_key, host_value in dict(defcfg_hosts).items():
            if host_key not in SUPPORTED_APPS._value2member_map_:  # pylint: disable=protected-access
                self.log(
                    logging.WARNING,
                    f"{where.capitalize()}: Unsupported host '{escape_single_quotes(host_key)}'. Discarding host.",
                )
                defcfg_hosts.pop(host_key, None)
                result = 1
            elif host_value is not None and (
                not isinstance(host_value, dict)
                or not all(k in ["attention", "scheduling", "alternation", "and", "break"] for k in host_value)
            ):
                self.log(
                    logging.WARNING,
                    f"{where.capitalize()}: Invalid format for host '{escape_single_quotes(host_key)}'. Discarding host.",
                )
                defcfg_hosts.pop(host_key, None)
                result = 1
        defcfg_models: dict[str, Any] = cfg.get("models", {})
        for model_key, model_value in dict(defcfg_models).items():
            if (
                not isinstance(model_value, dict)
                or model_value.get("detect") is None
                or not isinstance(model_value["detect"], dict)
            ):
                self.log(
                    logging.WARNING,
                    f"{where.capitalize()}: Invalid format for model '{escape_single_quotes(model_key)}'. Discarding model.",
                )
                defcfg_models.pop(model_key, None)
                result = 1
            else:
                defcfg_m_detect: dict[str, Any] = model_value["detect"]
                for host_key, host_value in dict(defcfg_m_detect).items():
                    if host_key not in SUPPORTED_APPS._value2member_map_:  # pylint: disable=protected-access
                        self.log(
                            logging.WARNING,
                            f"{where.capitalize()}: Unsupported host '{escape_single_quotes(host_key)}' in 'detect' for model '{escape_single_quotes(model_key)}'. Discarding host.",
                        )
                        defcfg_m_detect.pop(host_key, None)
                        result = 1
                    elif host_value is not None:
                        if not isinstance(host_value, dict):
                            self.log(
                                logging.WARNING,
                                f"{where.capitalize()}: Invalid format for host '{escape_single_quotes(host_key)}' in 'detect' for model '{escape_single_quotes(model_key)}'. Discarding host.",
                            )
                            defcfg_m_detect.pop(host_key, None)
                            result = 1
                        elif "class" in host_value:
                            if not isinstance(host_value["class"], list) or not all(
                                isinstance(c, str) for c in host_value["class"]
                            ):
                                self.log(
                                    logging.WARNING,
                                    f"{where.capitalize()}: Invalid format for 'class' in host '{escape_single_quotes(host_key)}' in 'detect' for model '{escape_single_quotes(model_key)}'. Discarding host.",
                                )
                                defcfg_m_detect.pop(host_key, None)
                                result = 1
                        elif "property" in host_value:
                            if not isinstance(host_value["property"], str):
                                self.log(
                                    logging.WARNING,
                                    f"{where.capitalize()}: Invalid format for 'property' in host '{escape_single_quotes(host_key)}' in 'detect' for model '{escape_single_quotes(model_key)}'. Discarding host.",
                                )
                                defcfg_m_detect.pop(host_key, None)
                                result = 1
                        else:
                            self.log(
                                logging.WARNING,
                                f"{where.capitalize()}: Neither 'class' nor 'property' specified for host '{escape_single_quotes(host_key)}' in 'detect' for model '{escape_single_quotes(model_key)}'. Discarding host.",
                            )
                            defcfg_m_detect.pop(host_key, None)
                            result = 1
                if "variants" in model_value:
                    if not isinstance(model_value["variants"], dict):
                        self.log(
                            logging.WARNING,
                            f"{where.capitalize()}: Invalid format for 'variants' in model '{escape_single_quotes(model_key)}'. Discarding model.",
                        )
                        defcfg_models.pop(model_key, None)
                        result = 1
                    else:
                        defcfg_m_variants: dict[str, Any] = model_value["variants"]
                        for variant_key, variant_value in dict(defcfg_m_variants).items():
                            if not isinstance(variant_key, str) or not variant_key.isidentifier():
                                self.log(
                                    logging.WARNING,
                                    f"{where.capitalize()}: Invalid variant name '{escape_single_quotes(variant_key)}' in model '{escape_single_quotes(model_key)}'. Discarding variant.",
                                )
                                defcfg_m_variants.pop(variant_key, None)
                                result = 1
                            elif not isinstance(variant_value, dict) or not isinstance(
                                variant_value.get("find_in_filename"), (str, dict, list)
                            ):
                                self.log(
                                    logging.WARNING,
                                    f"{where.capitalize()}: Invalid format for variant '{escape_single_quotes(variant_key)}' in model '{escape_single_quotes(model_key)}'. Discarding variant.",
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
        return hash(self.state.options)

    def interrupt(self):
        if self.interrupt_callback is not None:
            self.interrupt_callback()

    def __init_sysvars(self):
        """
        Initializes the system variables.
        """
        sv = self.state.system_variables
        sv.clear()
        sdchecks = {x: self.env_info.get("is_" + x, False) for x in self.known_models}
        sdchecks.update({"": True})
        sv["_model"] = next((k for k, v in sdchecks.items() if v), "")
        sv["_sd"] = sv["_model"]  # deprecated
        model_filename = self.env_info.get("model_filename", "")
        sv["_sdfullname"] = model_filename  # deprecated
        sv["_modelfullname"] = model_filename
        sv["_sdname"] = os.path.basename(model_filename)  # deprecated
        sv["_modelname"] = os.path.basename(model_filename)
        sv["_modelclass"] = self.env_info.get("model_class", "")
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
            self.log(
                logging.WARNING,
                f"Multiple model variants detected at the same time in the filename!: {', '.join(is_models_true)}",
            )
        sv.update({"_is_" + x: y for x, y in is_models.items()})
        for x in sdchecks.keys():
            if x != "":
                sv["_is_" + x] = sdchecks[x]
                sv["_is_pure_" + x] = sdchecks[x] and not any(is_models.values())
                sv["_is_variant_" + x] = sdchecks[x] and any(is_models.values())
        # special cases
        sv["_is_sd"] = sdchecks["sd1"] or sdchecks["sd2"] or sdchecks["sdxl"] or sdchecks["sd3"]
        is_ssd = self.env_info.get("is_ssd", False)
        sv["_is_ssd"] = is_ssd
        sv["_is_sdxl_no_ssd"] = sdchecks["sdxl"] and not is_ssd
        # backcompatibility (but the modern one to use would be _is_pure_sdxl)
        sv["_is_sdxl_no_pony"] = sdchecks["sdxl"] and not sv.get("_is_pony", False)

    def init_wildcards_options(self):
        """Initializes the wildcard options."""
        _tree = TreeProcessor(self.state, np.random.default_rng())
        for wc in self.state.wildcards_obj.wildcards.values():
            _tree.get_wildcard_options(wc)

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
                if (
                    negative_prompt[ipp - len(self.state.options.stn_separator) : ipp]
                    == self.state.options.stn_separator
                ):
                    ipp -= len(self.state.options.stn_separator)  # adjust for existing start separator
                    ipl += len(self.state.options.stn_separator)
                add_at_insertion_point[n].insert(0, negative_prompt[:ipp])
                if (
                    negative_prompt[ipp + ipl : ipp + ipl + len(self.state.options.stn_separator)]
                    == self.state.options.stn_separator
                ):
                    ipl += len(self.state.options.stn_separator)  # adjust for existing end separator
                endPart = negative_prompt[ipp + ipl :]
                if len(endPart) > 0:
                    add_at_insertion_point[n].append(endPart)
                negative_prompt = self.state.options.stn_separator.join(add_at_insertion_point[n])
            else:
                ipp = 0
                if negative_prompt.startswith(self.state.options.stn_separator):
                    ipp = len(self.state.options.stn_separator)
                add_at_insertion_point[n].append(negative_prompt[ipp:])
                negative_prompt = self.state.options.stn_separator.join(add_at_insertion_point[n])
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
            if negative_prompt.startswith(self.state.options.stn_separator):
                ipp = len(self.state.options.stn_separator)  # adjust for existing end separator
            add_at_start.append(negative_prompt[ipp:])
        negative_prompt = self.state.options.stn_separator.join(add_at_start)
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
            if negative_prompt.endswith(self.state.options.stn_separator):
                ipl -= len(self.state.options.stn_separator)  # adjust for existing start separator
            add_at_end.insert(0, negative_prompt[:ipl])
        negative_prompt = self.state.options.stn_separator.join(add_at_end)
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
        break_processing = self.state.host_config.get("break", "ok")
        # break_processing == "ok" (and always)
        if self.state.options.cup_breaks_eol:
            # replace spaces before break with EOL
            text = re.sub(r"[, ]+BREAK\b", "\nBREAK", text)
        if self.state.options.cup_breaks:
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
                self.log(logging.DEBUG, f"BREAK construct {break_replacements[break_processing][0]}")
        elif break_processing == "error":
            if re.search(r"\bBREAK\b", text):
                warn_or_stop(self.state, where == -1, "BREAK constructs are not allowed!")

        if self.state.options.cup_ands:
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

        escapedSeparator = re.escape(self.state.options.stn_separator)
        optwhitespace = r"\s*" if self.state.options.cup_extra_separators_include_eol else r"[ \t\v\f]*"
        optwhitespace_separator = optwhitespace + escapedSeparator + optwhitespace
        optwhitespace_comma = optwhitespace + "," + optwhitespace
        sep_options = [(optwhitespace_separator, self.state.options.stn_separator)]  # sendtonegative separator
        if optwhitespace_comma != optwhitespace_separator:
            sep_options.append((optwhitespace_comma, ", "))  # regular comma separator
        for sep, replacement in sep_options:
            if self.state.options.cup_extra_separators:
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
            if self.state.options.cup_extra_separators2:
                # remove at start of prompt or line
                text = re.sub(r"^(?:" + sep + r")+", "", text, flags=re.MULTILINE)
                # remove at end of prompt or line
                text = re.sub(r"(?:" + sep + r")+$", "", text, flags=re.MULTILINE)
        if self.state.options.cup_extranetwork_tags:
            # remove spaces before <
            text = re.sub(r"\B\s+<(?!!)", "<", text)
            # remove spaces after >
            text = re.sub(r">\s+\B", ">", text)
        if self.state.options.cup_extra_spaces:
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
                self.state.parsers["full"],
                "full parser with wildcards, choices, commands and variables",
            )
        if tests["ALLOW_WILDCARDS"] and tests["ALLOW_CHOICES"]:
            return (
                self.state.parsers["wc_ch"],
                "parser with wildcards and choices",
            )
        if tests["ALLOW_WILDCARDS"] and tests["ALLOW_COMMVARS"]:
            return (
                self.state.parsers["wc_cv"],
                "parser with wildcards, commands and variables",
            )
        if tests["ALLOW_CHOICES"] and tests["ALLOW_COMMVARS"]:
            return (
                self.state.parsers["ch_cv"],
                "parser with choices, commands and variables",
            )
        if tests["ALLOW_WILDCARDS"]:
            return (
                self.state.parsers["wc"],
                "parser with wildcards",
            )
        if tests["ALLOW_CHOICES"]:
            return (
                self.state.parsers["ch"],
                "parser with choices",
            )
        if tests["ALLOW_COMMVARS"]:
            return (
                self.state.parsers["cv"],
                "parser with commands and variables",
            )
        return (
            self.state.parsers["only_old"],
            "simple parser without new constructs",
        )

    def __processprompts(self, rng, prompt, negative_prompt):
        """
        Process the prompt and negative prompt.

        Args:
            rng (numpy.random.Generator): The random number generator.
            prompt (str): The prompt.
            negative_prompt (str): The negative prompt.

        Returns:
            tuple: A tuple containing the processed prompt and negative prompt.
        """
        self.state.user_variables.clear()
        self.state.echoed_variables.clear()
        all_variables = {**self.state.system_variables}

        # Process prompt
        p_processor = TreeProcessor(self.state, rng)
        (prompt_parser, parser_description) = self.__get_best_parser(prompt)
        self.log(logging.DEBUG, f"Using {parser_description} for prompt")
        p_parsed = parse_prompt(
            self.state,
            "prompt",
            prompt,
            prompt_parser,
        )
        prompt = p_processor.start_visit("prompt", p_parsed, False)

        # Process negative prompt
        n_processor = TreeProcessor(self.state, rng)
        (n_prompt_parser, n_parser_description) = self.__get_best_parser(negative_prompt)
        self.log(logging.DEBUG, f"Using {n_parser_description} for negative prompt")
        n_parsed = parse_prompt(
            self.state,
            "negative prompt",
            negative_prompt,
            n_prompt_parser,
        )
        negative_prompt = n_processor.start_visit("negative prompt", n_parsed, True)

        # Complete variables
        var_keys = set(self.state.user_variables.keys()).union(set(self.state.echoed_variables.keys()))
        for k in var_keys:
            ev = self.state.echoed_variables.get(k)
            if ev is None:
                ev = self.state.user_variables.get(k)
            if ev is None or not isinstance(ev, str):
                self.log(logging.DEBUG, f"Completing variable: {k}")
                ev = p_processor.get_final_user_variable(k)
            all_variables[k] = self.__cleanup(ev, 0) if self.state.options.cup_cleanup_variables else ev
        self.log(logging.DEBUG, f"All variables: {all_variables}")

        # Insertions in the negative prompt
        self.log(logging.DEBUG, f"New negative additions: {p_processor.add_at}")
        self.log(logging.DEBUG, f"New negative indexes: {n_processor.insertion_at}")
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
            if self.state.options.if_wildcards == IFWILDCARDS_CHOICES.stop:
                self.log(logging.ERROR, "Found unprocessed wildcards!")
            else:
                self.log(logging.INFO, "Found unprocessed wildcards.")
            ppwl = ", ".join(p_processor.detectedWildcards)
            npwl = ", ".join(n_processor.detectedWildcards)
            if foundP:
                self.log(logging.ERROR, f"In the positive prompt: {ppwl}")
            if foundNP:
                self.log(logging.ERROR, f"In the negative prompt: {npwl}")
            if self.state.options.if_wildcards == IFWILDCARDS_CHOICES.warn:
                prompt = self.WILDCARD_WARNING + prompt
            elif self.state.options.if_wildcards == IFWILDCARDS_CHOICES.stop:
                raise PPPInterrupt(
                    "Found unprocessed wildcards!",
                    self.WILDCARD_STOP.format(ppwl) if foundP else "",
                    self.WILDCARD_STOP.format(npwl) if foundNP else "",
                )

        # Check for special character sequences that should not be in the result
        compound_prompt = prompt + "\n" + negative_prompt
        found_sequences = re.findall(r"::|\$\$|\$\{|[{}]", compound_prompt)
        if found_sequences:
            self.log(
                logging.WARNING,
                f"""Found probably invalid character sequences on the result ({', '.join(map(lambda x: '"' + x + '"', set(found_sequences)))}). Something might be wrong!""",
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
            prompt = original_prompt
            negative_prompt = original_negative_prompt
            self.log(logging.INFO, f"System variables: {self.state.system_variables}")
            self.log(logging.INFO, f"Input seed: {seed}")
            self.log(logging.INFO, f"Input prompt: {prompt}")
            self.log(logging.INFO, f"Input negative_prompt: {negative_prompt}")
            t1 = time.monotonic_ns()
            prompt, negative_prompt, all_variables = self.__processprompts(
                np.random.default_rng(seed & 0xFFFFFFFF), prompt, negative_prompt
            )
            t2 = time.monotonic_ns()
            self.log(logging.INFO, f"Result prompt: {prompt}")
            self.log(logging.INFO, f"Result negative_prompt: {negative_prompt}")
            self.log(logging.INFO, f"Process prompt pair time: {(t2 - t1) / 1_000_000_000:.3f} seconds")

            # self.log(logging.DEBUG,f"Wildcards memory usage: {self.state.wildcards_obj.__sizeof__()}")
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
            self.log(logging.ERROR, e.message)
            if e.pos_prefix:
                prompt = e.pos_prefix + prompt
            if e.neg_prefix:
                negative_prompt = e.neg_prefix + negative_prompt
            self.log(logging.ERROR, "Interrupting!")
            self.interrupt()
            return prompt, negative_prompt, all_variables
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log(logging.ERROR, f"Unexpected error: {e}")
            return original_prompt, original_negative_prompt, all_variables
