import dataclasses
import logging
import os
import re
import time
from typing import Any, Callable, Optional
import lark
import numpy as np
import yaml

from pydantic import ValidationError
from ppp_classes import (
    FindInFilenamePattern,
    HostConfig,
    ModelConfig,
    ModelDetectConfig,
    VariantConfig,
    PPPConfig,
    IFWILDCARDS_CHOICES,
    SUPPORTED_APPS,
    PPPInterrupt,
    PPPState,
    PPPStateOptions,
)
from ppp_variables import VariableRepository
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
    DEFAULT_STRICT_OPERATORS = defopt["strict_operators"]
    DEFAULT_DO_COMBINATORIAL = defopt["do_combinatorial"]
    DEFAULT_COMBINATORIAL_SHUFFLE = defopt["combinatorial_shuffle"]
    DEFAULT_COMBINATORIAL_LIMIT = defopt["combinatorial_limit"]
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
                default_raw: dict[str, Any] = yaml.safe_load(f)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.config = {}
            raise PPPInterrupt(
                f"Failed to load default configuration from '{escape_single_quotes(default_config_file)}'."
            ) from exc
        self.config, def_result = self.__parse_configuration(default_raw, "default configuration file")
        if def_result != 0:
            errmsg = "Default configuration file has errors. Please restore the default configuration file and, per instructions, use a copy to adapt it."
            if def_result == 2:
                raise PPPInterrupt(errmsg)
            self.log(logging.WARNING, errmsg)

        user_config_file = self.env_info.get("ppp_config", "")
        if isinstance(user_config_file, dict):
            user_cfg, _ = self.__parse_configuration(user_config_file, "forced configuration")
        else:
            user_raw: dict[str, Any] = {}
            if user_config_file == "":
                if self.env_info.get("app", "") == SUPPORTED_APPS.comfyui.value:
                    try:
                        import folder_paths  # type: ignore

                        user_dir = folder_paths.get_user_directory()
                        if user_dir and os.path.isdir(user_dir):
                            user_config_file = os.path.join(user_dir, "default", "ppp_config.yaml")
                    except Exception:  # pylint: disable=broad-exception-caught
                        self.log(logging.WARNING, "Failed to get user directory for PPP config.")
                if not user_config_file or not os.path.exists(user_config_file):
                    user_config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ppp_config.yaml")
            if user_config_file and os.path.exists(user_config_file):
                with open(user_config_file, "r", encoding="utf-8") as f:
                    user_raw = yaml.safe_load(f)
                user_cfg, _ = self.__parse_configuration(user_raw, "user configuration")
            else:
                user_cfg = None
        if user_cfg is not None:
            self.__merge_configuration(user_cfg)

        self.models_config: dict[str, ModelConfig | None] = self.config.models or {}
        self.known_models: list[str] = list(self.models_config.keys())

        # Patch for tests (copy comfyui)
        if self.env_info.get("app", "") == "tests":
            if self.config.hosts is None:
                self.config.hosts = {}
            self.config.hosts.setdefault("tests", HostConfig())
            for m in self.known_models:
                model = self.models_config.get(m)
                if model is not None:
                    if model.detect is None:
                        model.detect = {}
                    model.detect.setdefault("tests", model.detect.get("comfyui", None))

        host_config: HostConfig | None = (self.config.hosts or {}).get(self.env_info.get("app", ""))
        if host_config is None:
            raise PPPInterrupt(
                f"No host configuration found for app '{escape_single_quotes(self.env_info.get('app', ''))}'. Please check your configuration."
            )

        # Update env_info with model detection
        prop_base = self.env_info.get("property_base", None)
        model_class = self.env_info.get("model_class", "")
        app = self.env_info.get("app", "")
        for m in self.known_models:
            self.env_info["is_" + m] = False
            model_obj = self.models_config.get(m)
            model_detect = (model_obj.detect if model_obj else None) or {}
            model_detect_for_app: ModelDetectConfig | None = model_detect.get(app)
            if model_detect_for_app is not None:
                cls_list = model_detect_for_app.class_ or []
                if model_class in cls_list:
                    self.env_info["is_" + m] = True
                elif model_detect_for_app.property is not None and prop_base is not None:
                    prop = model_detect_for_app.property
                    attr = getattr(prop_base, prop, None)
                    if isinstance(attr, bool) and attr:
                        self.env_info["is_" + m] = True
        self.variants_definitions: dict[str, tuple[str, list[FindInFilenamePattern]]] = {}
        for m in self.known_models:
            model_obj = self.models_config.get(m)
            for v, vo in ((model_obj.variants if model_obj else None) or {}).items():
                if v not in self.known_models:
                    self.variants_definitions[v] = (m, vo.find_in_filename)
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
            variables=VariableRepository(),
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

    def log(self, kind, message: str, min_level: DEBUG_LEVEL | None = None, exc_info: bool = False):
        log(self.logger, self.debug_level, kind, message, min_level, exc_info=exc_info)

    def __merge_configuration(self, user_config: PPPConfig):
        """
        Merges the user configuration into the default configuration.

        Args:
            user_config: The parsed user PPPConfig to merge into self.config.
        """
        if user_config.hosts:
            if self.config.hosts is None:
                self.config.hosts = {}
            # Options are replaced by host
            for host_key, host_value in user_config.hosts.items():
                self.config.hosts[host_key] = host_value
        if user_config.models:
            if self.config.models is None:
                self.config.models = {}
            for model_key, user_model in user_config.models.items():
                cfg_model = self.config.models.get(model_key)
                if user_model is None:
                    # User wants to disable this model: remove it
                    if cfg_model is not None:
                        self.config.models.pop(model_key, None)
                elif cfg_model is None:
                    # New model from user config: add with whatever was specified
                    self.config.models[model_key] = user_model
                else:
                    # Merge detect per-host
                    if "detect" in user_model.model_fields_set and user_model.detect is not None:
                        if cfg_model.detect is None:
                            cfg_model.detect = {}
                        for host, hdetect in user_model.detect.items():
                            cfg_model.detect[host] = hdetect
                    # Variants are fully replaced
                    if user_model.variants is not None:
                        cfg_model.variants = user_model.variants

    def __parse_configuration(self, cfg: dict[str, Any] | Any, where: str) -> tuple[PPPConfig, int]:
        """
        Parses and validates a raw configuration dict into a PPPConfig object.
        Logs warnings for invalid entries and discards them.

        Args:
            cfg: The raw configuration value to parse (expected to be a dict).
            where: Description of where this config came from (for logging).

        Returns:
            tuple[PPPConfig, int]: The parsed config and a result code:
                0 = valid, 1 = non-fatal warnings, 2 = fatal errors.
        """
        if not isinstance(cfg, dict):
            if cfg is not None:
                self.logger.error(f"{where.capitalize()}: is not a dictionary.")
                return PPPConfig(), 2
            return PPPConfig(), 0
        if cfg.get("hosts") and not isinstance(cfg["hosts"], dict):
            self.logger.error(f"{where.capitalize()}: 'hosts' is not a valid dictionary.")
            return PPPConfig(), 2
        if cfg.get("models") and not isinstance(cfg.get("models"), dict):
            self.logger.error(f"{where.capitalize()}: 'models' is not a valid dictionary.")
            return PPPConfig(), 2
        result = 0
        parsed_hosts: dict[str, HostConfig | None] = {}
        raw_hosts: dict[str, dict | None] = cfg.get("hosts") or {}
        for host_key, host_value in raw_hosts.items():
            if host_key not in SUPPORTED_APPS._value2member_map_:  # pylint: disable=protected-access
                self.logger.warning(
                    f"{where.capitalize()}: Unsupported host '{escape_single_quotes(host_key)}'. Discarding host."
                )
                result = 1
            elif host_value is None:
                parsed_hosts[host_key] = None
            else:
                try:
                    parsed_hosts[host_key] = HostConfig.model_validate(host_value)
                except ValidationError as exc:
                    self.logger.warning(
                        f"{where.capitalize()}: Invalid format for host '{escape_single_quotes(host_key)}': {exc}. Discarding host."
                    )
                    result = 1
        parsed_models: dict[str, ModelConfig | None] = {}
        raw_models: dict[str, dict | None] = cfg.get("models") or {}
        for model_key, model_value in raw_models.items():
            if not isinstance(model_value, dict) or not any(k in model_value for k in ("detect", "variants")):
                self.logger.warning(
                    f"{where.capitalize()}: Invalid format for model '{escape_single_quotes(model_key)}'. Discarding model."
                )
                result = 1
                continue
            parsed_detect: dict[str, ModelDetectConfig | None] | None = None
            if "detect" in model_value:
                if not isinstance(model_value["detect"], dict):
                    self.logger.warning(
                        f"{where.capitalize()}: Invalid format for 'detect' in model '{escape_single_quotes(model_key)}'. Discarding model."
                    )
                    result = 1
                    continue
                parsed_detect = {}
                for host_key, host_value in model_value["detect"].items():
                    if host_key not in SUPPORTED_APPS._value2member_map_:  # pylint: disable=protected-access
                        self.log(
                            logging.WARNING,
                            f"{where.capitalize()}: Unsupported host '{escape_single_quotes(host_key)}' in 'detect' for model '{escape_single_quotes(model_key)}'. Discarding host.",
                        )
                        result = 1
                    elif host_value is None:
                        parsed_detect[host_key] = None
                    else:
                        try:
                            parsed_detect[host_key] = ModelDetectConfig.model_validate(host_value)
                        except ValidationError as exc:
                            self.logger.warning(
                                f"{where.capitalize()}: Invalid format for host '{escape_single_quotes(host_key)}' in 'detect' for model '{escape_single_quotes(model_key)}': {exc}. Discarding host."
                            )
                            result = 1
            model_fields: dict[str, dict | None] = {}
            if parsed_detect is not None:
                model_fields["detect"] = parsed_detect
            if "variants" in model_value:
                if not isinstance(model_value["variants"], dict):
                    self.logger.warning(
                        f"{where.capitalize()}: Invalid format for 'variants' in model '{escape_single_quotes(model_key)}'. Discarding model."
                    )
                    result = 1
                    continue
                parsed_variants: dict[str, VariantConfig | None] = {}
                skip_model = False
                for variant_key, variant_value in model_value["variants"].items():
                    if not isinstance(variant_key, str) or not variant_key.isidentifier():
                        self.logger.warning(
                            f"{where.capitalize()}: Invalid variant name '{escape_single_quotes(variant_key)}' in model '{escape_single_quotes(model_key)}'. Discarding variant."
                        )
                        result = 1
                    else:
                        try:
                            parsed_variants[variant_key] = VariantConfig.model_validate(variant_value)
                        except ValidationError as exc:
                            self.logger.warning(
                                f"{where.capitalize()}: Invalid format for variant '{escape_single_quotes(variant_key)}' in model '{escape_single_quotes(model_key)}': {exc}. Discarding variant."
                            )
                            result = 1
                if skip_model:
                    continue
                model_fields["variants"] = parsed_variants or None
            parsed_models[model_key] = ModelConfig(**model_fields)
        return (
            PPPConfig(
                hosts=parsed_hosts or None,
                models=parsed_models or None,
            ),
            result,
        )

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
        vs = self.state.variables
        vs.clear_system()
        sdchecks = {x: self.env_info.get("is_" + x, False) for x in self.known_models}
        sdchecks.update({"": True})
        model_name_val = next((k for k, v in sdchecks.items() if v), "")
        vs.set_system("_model", model_name_val)
        vs.set_system("_sd", model_name_val)  # deprecated
        model_filename = self.env_info.get("model_filename", "")
        vs.set_system("_sdfullname", model_filename)  # deprecated
        vs.set_system("_modelfullname", model_filename)
        vs.set_system("_sdname", os.path.basename(model_filename))  # deprecated
        vs.set_system("_modelname", os.path.basename(model_filename))
        vs.set_system("_modelclass", self.env_info.get("model_class", ""))
        is_models = {}
        for model_name, model_type_and_substrings in self.variants_definitions.items():
            if not (model_type_and_substrings[0] == "" or sdchecks.get(model_type_and_substrings[0], False)):
                is_models[model_name] = False
            else:
                is_models[model_name] = any(
                    (re.search(dre.regex, model_filename, dre.flags) is not None)
                    for dre in model_type_and_substrings[1]
                )
        is_models_true = [k for k, v in is_models.items() if v]
        if len(is_models_true) > 1:
            self.log(
                logging.WARNING,
                f"Multiple model variants detected at the same time in the filename!: {', '.join(is_models_true)}",
            )
        vs.update_system({"_is_" + x: y for x, y in is_models.items()})
        for x in sdchecks.keys():
            if x != "":
                vs.set_system("_is_" + x, sdchecks[x])
                vs.set_system("_is_pure_" + x, sdchecks[x] and not any(is_models.values()))
                vs.set_system("_is_variant_" + x, sdchecks[x] and any(is_models.values()))
        # special cases
        vs.set_system("_is_sd", sdchecks["sd1"] or sdchecks["sd2"] or sdchecks["sdxl"] or sdchecks["sd3"])
        is_ssd = self.env_info.get("is_ssd", False)
        vs.set_system("_is_ssd", is_ssd)
        vs.set_system("_is_sdxl_no_ssd", sdchecks["sdxl"] and not is_ssd)
        # backcompatibility (but the modern one to use would be _is_pure_sdxl)
        vs.set_system("_is_sdxl_no_pony", sdchecks["sdxl"] and not vs.get_system("_is_pony", False))

    def init_wildcards_options(self):
        """Initializes the wildcard options."""
        _tree = TreeProcessor(self.state, np.random.default_rng())
        for wc in self.state.wildcards_obj.wildcards.values():
            _tree.get_wildcard_options(wc)

    def __cleanup(self, text: str, where: int = 0) -> str:
        """
        Trims the given text based on the specified cleanup options.

        Args:
            text (str): The text to be cleaned up.
            where (int): Indicates the context or position for cleanup (0=generic, -1=negative prompt, 1=positive prompt).

        Returns:
            str: The resulting text.
        """
        break_processing = self.state.host_config.break_
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

    def __postprocess_result(
        self,
        result: tuple[str, list[tuple[str, bool]], tuple[dict[str, str | None], dict[str, str | None]]],
    ) -> tuple[str, str, dict[str, str | None]]:
        variables = {}
        unified_prompt, rem_wildcards, (_, echoed_variables_snapshot) = result

        # Split the unified prompt back into prompt and negative prompt
        split_parts = unified_prompt.split("\x1d", 1)
        prompt = split_parts[0]
        negative_prompt = split_parts[1] if len(split_parts) > 1 else ""

        # Clean up
        prompt = self.__cleanup(prompt, 1)
        negative_prompt = self.__cleanup(negative_prompt, -1)

        self.log(logging.INFO, f"Result prompt: {prompt}")
        self.log(logging.INFO, f"Result negative_prompt: {negative_prompt}")
        try:
            # Get and clean variables
            var_keys = sorted(echoed_variables_snapshot.keys())
            for k in var_keys:
                ev = echoed_variables_snapshot.get(k)
                variables[k] = self.__cleanup(ev, 0) if self.state.options.cup_cleanup_variables else ev

            self.log(logging.DEBUG, f"Result variables: {variables}")

            # Result checks
            warnings = []

            # Check for special character sequences that should not be in the result
            compound_prompt = prompt + "\n" + negative_prompt
            found_sequences = re.findall(r"::|\$\$|\$\{|[{}]", compound_prompt)
            if found_sequences:
                s = ", ".join(map(lambda x: '"' + x + '"', set(found_sequences)))
                warnings.append(f"Probably invalid character sequences: {s}.")
            # Check for correctly nested parentheses and brackets
            stack = []
            prev_char = ""
            for char in compound_prompt:
                if prev_char != "\\":
                    if char in "([":  # opening characters
                        stack.append(char)
                    elif char in ")]":  # closing characters
                        if not stack:
                            warnings.append(f"Unmatched '{char}' character.")
                            break
                        last_open = stack.pop()
                        if (last_open == "(" and char != ")") or (last_open == "[" and char != "]"):
                            warnings.append(f"Mismatched '{last_open}' and '{char}' characters.")
                            break
                    prev_char = char
                else:
                    prev_char = ""  # reset prev_char to avoid treating escaped characters as escapes
            if stack:
                warnings.append(f"Unmatched '{''.join(stack)}' characters.")
            if warnings:
                self.log(
                    logging.WARNING,
                    "Found some weird things in the result. Something might be wrong!\n"
                    + "\n".join(f"  - {w}" for w in warnings),
                )

            # Check for wildcards not processed
            if rem_wildcards:
                w_found_p = [wc for wc, n in rem_wildcards if not n]
                w_found_n = [wc for wc, n in rem_wildcards if n]
                if self.state.options.if_wildcards == IFWILDCARDS_CHOICES.stop:
                    self.log(logging.ERROR, "Found unprocessed wildcards!")
                else:
                    self.log(logging.INFO, "Found unprocessed wildcards.")
                ppwl = ", ".join(w_found_p)
                npwl = ", ".join(w_found_n)
                if ppwl:
                    self.log(logging.ERROR, f"In the prompt: {ppwl}")
                if npwl:
                    self.log(logging.ERROR, f"In the negative prompt: {npwl}")
                if self.state.options.if_wildcards == IFWILDCARDS_CHOICES.warn:
                    prompt = self.WILDCARD_WARNING + prompt
                elif self.state.options.if_wildcards == IFWILDCARDS_CHOICES.stop:
                    raise PPPInterrupt(
                        "Found unprocessed wildcards!",
                        self.WILDCARD_STOP.format(ppwl) if ppwl else "",
                        self.WILDCARD_STOP.format(npwl) if npwl else "",
                    )

            # Check for constructs not processed due to parsing problems
            ppp_in_prompt = prompt.find("<ppp:") >= 0
            ppp_in_negative_prompt = negative_prompt.find("<ppp:") >= 0
            if ppp_in_prompt or ppp_in_negative_prompt:
                raise PPPInterrupt(
                    "Found unprocessed constructs!",
                    self.UNPROCESSED_STOP if ppp_in_prompt else "",
                    self.UNPROCESSED_STOP if ppp_in_negative_prompt else "",
                )
        except PPPInterrupt as e:
            self.log(logging.ERROR, e.message)
            if e.pos_prefix:
                prompt = e.pos_prefix + prompt
            if e.neg_prefix:
                negative_prompt = e.neg_prefix + negative_prompt
            self.log(logging.ERROR, "Interrupting!")
            self.interrupt()

        v = self.state.variables.get_all_system()
        v.update(variables)
        return prompt, negative_prompt, v

    def __processprompts(
        self, rng: np.random.Generator, prompt: str, negative_prompt: str
    ) -> list[tuple[str, str, dict[str, str | None]]]:
        """
        Process the prompt and negative prompt.

        Args:
            rng (numpy.random.Generator): The random number generator.
            prompt (str): The prompt.
            negative_prompt (str): The negative prompt.

        Returns:
            list: A list of tuples, each containing the processed prompt, negative prompt, and all variables.
        """
        self.state.variables.clear_user()
        self.state.variables.clear_echoed()

        # Parse both prompts
        processor = TreeProcessor(self.state, rng)
        unified_prompt = prompt + "\x1d" + negative_prompt
        prompt_parser, parser_description = self.__get_best_parser(unified_prompt)
        self.log(logging.DEBUG, f"Using {parser_description} for prompt")
        parsed = parse_prompt(
            self.state,
            "prompt",
            unified_prompt,
            prompt_parser,
        )

        # Process the unified prompt
        t1 = time.monotonic_ns()
        try:
            results = processor.start_visit(parsed)
        except PPPInterrupt as e:
            results = []
            self.log(logging.ERROR, e.message)
            if e.pos_prefix:
                prompt = e.pos_prefix + prompt
            if e.neg_prefix:
                negative_prompt = e.neg_prefix + negative_prompt
            self.log(logging.ERROR, "Interrupting!")
            self.interrupt()
        t2 = time.monotonic_ns()
        self.log(logging.INFO, f"Visit time: {(t2 - t1) / 1_000_000_000:.3f} seconds")

        final_results = []
        for i, r in enumerate(results):
            if self.state.options.do_combinatorial:
                self.log(logging.INFO, f"Combination {i + 1}:")
            final_results.append(self.__postprocess_result(r))
        if self.state.options.do_combinatorial:
            self.log(logging.INFO, f"Total combinations: {len(final_results)}")
            if self.state.options.combinatorial_shuffle:
                rng.shuffle(final_results)
                self.log(logging.INFO, "Combinations shuffled")
        return final_results

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
        try:
            if seed == -1:
                seed = np.random.randint(0, 2**32, dtype=np.int64)
            prompt = original_prompt
            negative_prompt = original_negative_prompt
            self.log(logging.INFO, f"System variables: {self.state.variables.get_all_system()}")
            self.log(logging.INFO, f"Input seed: {seed}")
            self.log(logging.INFO, f"Input prompt: {prompt}")
            self.log(logging.INFO, f"Input negative_prompt: {negative_prompt}")
            self.log(logging.INFO, f"Combinatorial: {self.state.options.do_combinatorial}")
            t1 = time.monotonic_ns()
            results = self.__processprompts(np.random.default_rng(seed & 0xFFFFFFFF), prompt, negative_prompt)
            t2 = time.monotonic_ns()
            self.log(logging.INFO, f"Process prompt pair time: {(t2 - t1) / 1_000_000_000:.3f} seconds")
            # self.log(logging.DEBUG,f"Wildcards memory usage: {self.state.wildcards_obj.__sizeof__()}")
            return results
        except PPPInterrupt as e:
            self.log(logging.ERROR, e.message)
            if e.pos_prefix:
                prompt = e.pos_prefix + prompt
            if e.neg_prefix:
                negative_prompt = e.neg_prefix + negative_prompt
            self.log(logging.ERROR, "Interrupting!")
            self.interrupt()
            return [(prompt, negative_prompt, {})]
        except Exception:  # pylint: disable=broad-exception-caught
            self.log(logging.ERROR, "Unexpected error", exc_info=True)
            return [(original_prompt, original_negative_prompt, {})]
