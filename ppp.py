import csv
import dataclasses
from datetime import datetime
from enum import Enum
from io import StringIO
import json
import logging
from pathlib import Path
import re
import textwrap
import time
from typing import Any, Callable, Optional
import lark
import numpy as np
from ruamel.yaml import YAML as _YAML

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
    PPPStateInputs,
)
from ppp_variables import VariableRepository, VariableEntry, VariableValue
from ppp_logging import DEBUG_LEVEL, log
from ppp_tree import TreeProcessor
from ppp_utils import escape_single_quotes, get_version_from_pyproject
from ppp_common import get_model_class_from_filename, load_grammar, parse_prompt, preprocess_grammar, warn_or_stop
from ppp_wildcards import PPPWildcards
from ppp_enmappings import PPPExtraNetworkMappings


class PromptPostProcessor:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """
    The PromptPostProcessor class is responsible for processing and manipulating prompt strings.
    """

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
    DEFAULT_RESULTS_FILE = defopt["results_file"]

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

        host_config = self.__load_config_and_detect(env_info)

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
            env_info=env_info,
            host_config=host_config,
            options=options,
            inputs=PPPStateInputs(),
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
                "wc_filter_or": lark.Lark(
                    grammar_content_full,
                    propagate_positions=True,
                    start="wc_filter_or",
                ),
            },
        )
        self.__init_sysvars()

    def log(self, kind, message: str, min_level: DEBUG_LEVEL | None = None, exc_info=None):
        log(self.logger, self.debug_level, kind, message, min_level, exc_info=exc_info)

    def __load_config_and_detect(self, env_info: dict[str, Any]) -> HostConfig:
        """Loads config files, performs model detection, and returns the resolved host config."""
        main_folder = Path(__file__).resolve().parent
        default_config_file = str(main_folder / "ppp_config.yaml.defaults")
        _yaml_rt = _YAML()
        try:
            with open(default_config_file, "r", encoding="utf-8") as f:
                default_raw: dict[str, Any] = _yaml_rt.load(f)
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

        app = env_info.get("app", "")
        user_config_file = env_info.get("ppp_config", "")
        if isinstance(user_config_file, dict):
            user_cfg, _ = self.__parse_configuration(user_config_file, "forced configuration")
        else:
            if user_config_file == "":
                if app == SUPPORTED_APPS.comfyui.value:
                    try:
                        import folder_paths  # type: ignore

                        user_dir = folder_paths.get_user_directory()
                        if user_dir and Path(user_dir).is_dir():
                            user_config_file = str(Path(user_dir) / "default" / "ppp_config.yaml")
                    except Exception:  # pylint: disable=broad-exception-caught
                        self.log(logging.WARNING, "Failed to get user directory for PPP config.")
                if not user_config_file or not Path(user_config_file).exists():
                    user_config_file = str(main_folder / "ppp_config.yaml")
            if user_config_file and Path(user_config_file).exists():
                user_raw: dict[str, Any] = {}
                with open(user_config_file, "r", encoding="utf-8") as f:
                    user_raw = _yaml_rt.load(f)
                user_cfg, _ = self.__parse_configuration(user_raw, "user configuration")
                default_hosts = set((self.config.hosts or {}).keys())
                user_hosts = set((user_cfg.hosts or {}).keys())
                missing_hosts = default_hosts - user_hosts
                default_models = set((self.config.models or {}).keys())
                user_models = set((user_cfg.models or {}).keys())
                missing_models = default_models - user_models
                if user_raw is not None and (missing_hosts or missing_models):
                    raw_default_hosts = (default_raw or {}).get("hosts") or {}
                    raw_default_models = (default_raw or {}).get("models") or {}
                    if missing_hosts:
                        self.log(
                            logging.INFO,
                            f"Adding missing host(s) from default to user configuration: {', '.join(sorted(missing_hosts))}",
                        )
                        if not user_raw.get("hosts"):
                            user_raw["hosts"] = {}
                        for host in sorted(missing_hosts):
                            if host in raw_default_hosts:
                                user_raw["hosts"][host] = raw_default_hosts[host]
                    if missing_models:
                        self.log(
                            logging.INFO,
                            f"Adding missing model(s) from default to user configuration: {', '.join(sorted(missing_models))}",
                        )
                        if not user_raw.get("models"):
                            user_raw["models"] = {}
                        for model in sorted(missing_models):
                            if model in raw_default_models:
                                user_raw["models"][model] = raw_default_models[model]
                    try:
                        with open(user_config_file, "w", encoding="utf-8") as f:
                            _yaml_rt.dump(user_raw, f)
                        user_cfg, _ = self.__parse_configuration(user_raw, "user configuration")
                        self.log(
                            logging.INFO,
                            f"Saved updated user configuration to '{escape_single_quotes(user_config_file)}'.",
                        )
                    except Exception as exc:  # pylint: disable=broad-exception-caught
                        self.log(logging.WARNING, f"Failed to save updated user configuration: {exc}")
            else:
                user_cfg = None
        if user_cfg is not None:
            self.__merge_configuration(user_cfg)

        self.models_config: dict[str, ModelConfig | None] = self.config.models or {}
        self.known_models: list[str] = list(self.models_config.keys())

        # Patch for tests (copy comfyui)
        if app == "tests":
            if self.config.hosts is None:
                self.config.hosts = {}
            self.config.hosts.setdefault("tests", HostConfig())
            for m in self.known_models:
                model = self.models_config.get(m)
                if model is not None:
                    if model.detect is None:
                        model.detect = {}
                    model.detect.setdefault("tests", model.detect.get("comfyui", None))

        host_config: HostConfig | None = (self.config.hosts or {}).get(app)
        if host_config is None:
            raise PPPInterrupt(
                f"No host configuration found for app '{escape_single_quotes(app)}'. Please check your configuration."
            )

        # Update env_info with model detection
        self.__run_model_detection(env_info)
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
        self.log(
            logging.DEBUG,
            f"Host configuration ({escape_single_quotes(app)}): {host_config}",
            min_level=DEBUG_LEVEL.minimal,
        )

        return host_config

    def __run_model_detection(self, env_info: dict[str, Any]) -> None:
        """Updates the is_* model detection flags in env_info based on model_class."""
        prop_base = env_info.get("property_base", None)
        model_class = env_info.get("model_class", "")
        model_name = env_info.get("model_filename", "")
        app = env_info.get("app", "")
        if not model_class and model_name and app == SUPPORTED_APPS.comfyui.value:
            model_class = get_model_class_from_filename(model_name)
            if model_class:
                env_info["model_class"] = model_class
                self.log(
                    logging.DEBUG,
                    f"Detected model class '{model_class}' from filename '{model_name}'",
                    min_level=DEBUG_LEVEL.minimal,
                )
        for m in self.known_models:
            env_info["is_" + m] = False
            model_obj = self.models_config.get(m)
            model_detect = (model_obj.detect if model_obj else None) or {}
            model_detect_for_app: ModelDetectConfig | None = model_detect.get(app)
            if model_detect_for_app is not None:
                cls_list = model_detect_for_app.class_ or []
                if model_class and model_class in cls_list:
                    env_info["is_" + m] = True
                elif model_detect_for_app.property is not None and prop_base is not None:
                    prop = model_detect_for_app.property
                    attr = getattr(prop_base, prop, None)
                    if isinstance(attr, bool) and attr:
                        env_info["is_" + m] = True

    def __on_model_info_update(self) -> None:
        """Called when _modelfullname or _modelclass are set via a prompt command."""
        self.__run_model_detection(self.state.env_info)
        self.__init_sysvars()
        self.log(logging.DEBUG, f"Updated system variables: {self.state.variables.all_system}")

    def update(
        self,
        env_info: dict[str, Any],
        options: PPPStateOptions,
        wildcards_obj: PPPWildcards,
        extranetwork_mappings_obj: PPPExtraNetworkMappings,
    ) -> None:
        """Updates env_info, options, wildcards and enmappings while preserving the inputs, cyclical state and compiled parsers."""
        self.debug_level = options.debug_level
        host_config = self.__load_config_and_detect(env_info)
        self.state = PPPState(
            logger=self.logger,
            env_info=env_info,
            host_config=host_config,
            options=options,
            inputs=self.state.inputs,
            variables=VariableRepository(),
            wildcards_obj=wildcards_obj,
            extranetwork_mappings_obj=extranetwork_mappings_obj,
            parsers=self.state.parsers,
            cyclical_state=self.state.cyclical_state,
        )
        self.__init_sysvars()

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
                    # User wants to disable this model: keep the key as None so _is_* variables
                    # are still set to False (rather than being undefined)
                    self.config.models[model_key] = None
                elif cfg_model is None:
                    # New model from user config: add with whatever was specified
                    self.config.models[model_key] = user_model
                else:
                    # Merge detect per-host
                    # model_fields_set contains only fields the user explicitly supplied,
                    # so checking it prevents a missing "detect" key from erasing default detection rules.
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
            if model_value is None:
                parsed_models[model_key] = None
                continue
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

    @property
    def envinfo_hash(self) -> str:
        """
        Generates a hash string based on the environment information.

        Returns:
            str: A hash string representing the environment information.
        """
        return hash(tuple(sorted(self.state.env_info.items())))

    @property
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

        # We keep any existing input variables
        input_vars = {k: v for k, v in vs.all_system.items() if k.startswith("_input_")}
        vs.clear_system()

        # Option related variables
        for opt_name in self.defopt.keys():
            opt_value = getattr(self.state.options, opt_name)
            var_name = "_opt_" + opt_name
            if isinstance(opt_value, (bool, str, int, float)):
                vs.set_system(var_name, opt_value)
            elif isinstance(opt_value, Enum):
                vs.set_system(var_name, str(opt_value).split(".", 1)[-1])

        # Model related variables
        sdchecks = {x: self.state.env_info.get("is_" + x, False) for x in self.known_models}
        # Adding "" as a sentinel that is always True lets next() return "" when no model matches,
        # giving a well-defined empty-string fallback without a separate None check.
        sdchecks.update({"": True})
        model_name_val = next((k for k, v in sdchecks.items() if v), "")
        vs.set_system("_model", model_name_val)
        vs.set_system("_sd", model_name_val)  # deprecated
        model_filename = self.state.env_info.get("model_filename", "")
        vs.set_system("_sdfullname", model_filename)  # deprecated
        vs.set_system("_modelfullname", model_filename)
        vs.set_system("_sdname", Path(model_filename).name)  # deprecated
        vs.set_system("_modelname", Path(model_filename).name)
        vs.set_system("_modelclass", self.state.env_info.get("model_class", ""))
        is_models = {}
        for model_name, model_type_and_substrings in self.variants_definitions.items():
            # A variant is only active when its parent model type is currently loaded
            # (or when the variant has no parent restriction, indicated by an empty string).
            # If the parent is not active, short-circuit to False before testing filename patterns.
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
                # _is_pure_X: model X is active but no named variant matched the filename
                # _is_variant_X: model X is active AND at least one named variant matched
                vs.set_system("_is_pure_" + x, sdchecks[x] and not any(is_models.values()))
                vs.set_system("_is_variant_" + x, sdchecks[x] and any(is_models.values()))
        # special cases
        vs.set_system("_is_sd", sdchecks.get("sd1", False) or sdchecks.get("sd2", False) or sdchecks.get("sdxl", False) or sdchecks.get("sd3", False))
        is_ssd = self.state.env_info.get("is_ssd", False)
        vs.set_system("_is_ssd", is_ssd)
        vs.set_system("_is_sdxl_no_ssd", sdchecks.get("sdxl", False) and not is_ssd)
        # backcompatibility (but the modern one to use would be _is_pure_sdxl)
        vs.set_system("_is_sdxl_no_pony", sdchecks.get("sdxl", False) and not vs.get_system("_is_pony", False))

        vs.update_system(input_vars)

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
        # When EOL inclusion is on, use \s* so newlines are treated as whitespace around separators.
        # Otherwise, restrict to horizontal whitespace only to preserve intentional line breaks.
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
        result: tuple[str, list[tuple[str, bool]], dict[str, VariableEntry]],
    ) -> tuple[str, str, dict[str, str | None]]:
        all_variables = self.state.variables.all_system
        unechoed_variables: list[str] = []
        unified_prompt, rem_wildcards, variables_snapshot = result

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
            # Get and clean variables - prefer the explicitly echoed value; fall back to the evaluated value.
            var_keys = sorted(variables_snapshot.keys())
            for k in var_keys:
                entry = variables_snapshot[k]
                if entry.last_echoed_evaluated_value is None and entry.value is not None:
                    unechoed_variables.append(k)
                ev = entry.last_echoed_evaluated_value if entry.last_echoed_evaluated_value is not None else entry.value
                if ev is not None:
                    if isinstance(ev, str) and self.state.options.cup_cleanup_variables:
                        ev = self.__cleanup(ev, 0)
                    all_variables[k] = ev

            self.log(logging.INFO, f"Result variables: {all_variables}")
            if unechoed_variables:
                unechoed_values = {k: v for k, v in all_variables.items() if k in unechoed_variables}
                self.log(
                    logging.INFO,
                    f"Variables that were never echoed: {unechoed_values}",
                )

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
                    "Found some weird things in the result. Something might be wrong!: " + ", ".join(warnings),
                )

            # Check for wildcards not processed
            if rem_wildcards:
                w_found_p = [wc for wc, n in rem_wildcards if not n]
                w_found_n = [wc for wc, n in rem_wildcards if n]
                ppwl = ", ".join(w_found_p)
                npwl = ", ".join(w_found_n)
                if ppwl:
                    self.log(logging.WARN, f"Unprocessed wildcards in the prompt: {ppwl}")
                if npwl:
                    self.log(logging.WARN, f"Unprocessed wildcards in the negative prompt: {npwl}")
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

        return prompt, negative_prompt, all_variables

    def __processprompts(
        self,
        prompt: str,
        negative_prompt: str,
        seed: int,
        jobinfo: Any = None,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """
        Process the prompt and negative prompt.

        Args:
            prompt (str): The prompt.
            negative_prompt (str): The negative prompt.
            seed (int): The seed for the random number generator.

        Returns:
            list[tuple[str, str, dict[str, Any]]]: A list of tuples, each containing the processed prompt, negative prompt, and all variables.
        """
        self.state.variables.clear_user()

        # We update the input state
        # Truncate the seed to the host's configured bit width (-1 because we only want
        # positive numbers) so the value stays within the range the host expects
        # (e.g., 32-bit for SD-WebUI, 64-bit for ComfyUI).
        self.state.inputs.seed = int(seed & ((1 << (self.state.host_config.seed_bits - 1)) - 1))
        self.state.inputs.pos_prompt = prompt
        self.state.inputs.neg_prompt = negative_prompt
        self.state.inputs.jobinfo = jobinfo

        # Input related system variables
        for input_name in self.state.inputs.__dict__.keys():
            input_value = getattr(self.state.inputs, input_name)
            var_name = "_input_" + input_name
            if input_value is None:
                self.state.variables.set_system(var_name, None)
            elif isinstance(input_value, VariableValue):
                self.state.variables.set_system(var_name, input_value)
            elif isinstance(input_value, dict):
                for k, v in input_value.items():
                    self.state.variables.set_system(f"{var_name}_{k}", str(v))
            elif isinstance(input_value, Enum):
                self.state.variables.set_system(var_name, str(input_value).split(".", 1)[-1])
            else:
                self.log(
                    logging.WARNING,
                    f"Input '{input_name}' has an unsupported type {type(input_value).__name__} for a system variable and will be skipped.",
                )

        filtered_sysvars_inputs = {k: v for k, v in self.state.variables.all_system.items() if k.startswith("_input_")}
        self.log(logging.INFO, f"Inputs: {filtered_sysvars_inputs}")

        rng = np.random.default_rng(self.state.inputs.seed)

        # Parse both prompts
        processor = TreeProcessor(self.state, rng, on_model_info_update=self.__on_model_info_update)
        # We use the ASCII Group Separator character between prompt and negative prompt since it's unlikely to appear in prompts
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

        final_results: list[tuple[str, str, dict[str, Any]]] = []
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

    def process_prompts_group_start(self):
        """Start of a prompt processing group."""
        filtered_sysvars = {k: v for k, v in self.state.variables.all_system.items() if not k.startswith("_input_")}
        self.log(logging.DEBUG, f"System variables: {filtered_sysvars}")
        self.log(logging.INFO, f"Combinatorial: {self.state.options.do_combinatorial}")

    def _expand_filename(self) -> Path:
        """Expand %...% tokens in a filename template and resolve relative paths against the extension logs folder."""
        now = datetime.now()
        substitutions = {
            r"%datetime%": now.strftime(r"%Y-%m-%d_%H-%M-%S"),
            r"%date%": now.strftime(r"%Y-%m-%d"),
            r"%time%": now.strftime(r"%H-%M-%S"),
            r"%host%": str(self.state.env_info.get("app", "")),
        }
        result = str(self.state.options.results_file)
        for token, value in substitutions.items():
            result = result.replace(token, value)
        path = Path(result)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / "logs" / path
        return path

    def __save_results(self, results: list[tuple[str, str, dict[str, Any]]]) -> None:
        """Append processing results to the configured results file."""
        if not self.state.options.results_file:
            return
        try:
            filepath = self._expand_filename()
            self.log(logging.INFO, f"Saving results to file: {filepath}")
            ext = filepath.suffix.lower()
            records = []
            for result_prompt, result_neg_prompt, all_variables in results:
                records.append(
                    {
                        "options": {
                            k.removeprefix("_opt_"): v for k, v in all_variables.items() if k.startswith("_opt_")
                        },
                        "system_variables": {
                            k: v
                            for k, v in all_variables.items()
                            if k.startswith("_") and not k.startswith("_opt_") and not k.startswith("_input_")
                        },
                        "inputs": {
                            k.removeprefix("_input_"): v for k, v in all_variables.items() if k.startswith("_input_")
                        },
                        "prompt_results": {"prompt": result_prompt, "negative_prompt": result_neg_prompt},
                        "user_variables": {k: v for k, v in all_variables.items() if not k.startswith("_")},
                    }
                )
            filepath.parent.mkdir(parents=True, exist_ok=True)
            file_exists = filepath.exists()
            if ext in (".yaml", ".yml"):
                with open(filepath, "a", encoding="utf-8-sig") as f:
                    if not file_exists:
                        f.write("records:\n")
                    _yaml_dump = _YAML()
                    _yaml_dump.default_flow_style = False
                    for record in records:
                        _sio = StringIO()
                        _yaml_dump.dump(record, _sio)
                        y = _sio.getvalue()
                        f.write(f"  - {textwrap.indent(y, ' ' * 4).strip()}\n")
            elif ext == ".jsonl":
                with open(filepath, "a", encoding="utf-8-sig") as f:
                    for record in records:
                        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            elif ext == ".csv":
                # Build ordered column list from the current batch - header written only on new file.
                # Columns from later calls that weren't in the original header will be silently dropped.
                # The 'variables' section is serialized as a single JSON string column.
                all_columns: list[str] = []
                for record in records:
                    for section, data in record.items():
                        if section == "user_variables":
                            if "user_variables" not in all_columns:
                                all_columns.append("user_variables")
                        else:
                            for k in data:
                                col = f"{section}.{k}"
                                if col not in all_columns:
                                    all_columns.append(col)
                with open(filepath, "a", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=all_columns, delimiter=";", restval="", extrasaction="ignore")
                    if not file_exists:
                        writer.writeheader()
                    for record in records:
                        row: dict[str, Any] = {}
                        for section, data in record.items():
                            if section == "user_variables":
                                row["user_variables"] = json.dumps(data, ensure_ascii=False, default=str)
                            else:
                                for k, v in data.items():
                                    row[f"{section}.{k}"] = (
                                        v if isinstance(v, (str, int, float, bool)) or v is None else str(v)
                                    )
                        writer.writerow(row)
            else:  # plain text
                with open(filepath, "a", encoding="utf-8-sig") as f:
                    for record in records:
                        for section, data in record.items():
                            f.write(f"[{section}]\n")
                            for k, v in data.items():
                                f.write(f"{k}: {v}\n")
                        f.write(f"#{'-'*70}\n")
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log(logging.WARNING, "Failed to save results to file", exc_info=e)

    def process_prompt(
        self,
        original_prompt: str,
        original_negative_prompt: str,
        seed: int = -1,
        jobinfo: Any = None,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """
        Initializes the random number generator and processes the prompt and negative prompt.

        Args:
            original_prompt (str): The original prompt.
            original_negative_prompt (str): The original negative prompt.
            seed (int): The seed.
            jobinfo (Any): Optional job information, available as `_input_jobinfo`.

        Returns:
            list[tuple[str, str, dict[str, Any]]]: A list of tuples containing the processed prompt, negative prompt and all the prompt variables.
        """
        results: list[tuple[str, str, dict[str, Any]]]
        try:
            if seed == -1:
                seed = np.random.randint(0, 2 ** (self.state.host_config.seed_bits - 1), dtype=np.int64)
            prompt = original_prompt
            negative_prompt = original_negative_prompt
            t1 = time.monotonic_ns()
            if self.state.cyclical_state.last_prompt_pair != (original_prompt, original_negative_prompt):
                self.state.cyclical_state.reset()
                self.state.cyclical_state.last_prompt_pair = (original_prompt, original_negative_prompt)
            results = self.__processprompts(prompt, negative_prompt, seed, jobinfo)
            t2 = time.monotonic_ns()
            self.log(logging.INFO, f"Process prompt pair time: {(t2 - t1) / 1_000_000_000:.3f} seconds")
            # self.log(logging.DEBUG,f"Wildcards memory usage: {self.state.wildcards_obj.__sizeof__()}")
            self.__save_results(results)
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
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.log(logging.ERROR, "Unexpected error", exc_info=e)
            return [(original_prompt, original_negative_prompt, {})]

    def process_prompts_group_end(self):
        """End of a prompt processing group."""
