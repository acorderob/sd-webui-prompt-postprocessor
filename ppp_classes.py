"""Pydantic models for the PPP configuration file structure (ppp_config.yaml)."""

from dataclasses import dataclass, field
from logging import Logger
import re
from enum import Enum
from typing import Any, Literal, Optional
from lark import Lark
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ppp_logging import DEBUG_LEVEL
from ppp_wildcards import PPPWildcards
from ppp_enmappings import PPPExtraNetworkMappings


class SUPPORTED_APPS(Enum):
    comfyui = "comfyui"
    a1111 = "a1111"
    forge = "forge"
    reforge = "reforge"
    sdnext = "sdnext"
    tests = "tests"  # for testing purposes only, not a real app


SUPPORTED_APPS_NAMES = {
    SUPPORTED_APPS.comfyui: "ComfyUI",
    SUPPORTED_APPS.sdnext: "SD.Next",
    SUPPORTED_APPS.forge: "Forge",
    SUPPORTED_APPS.reforge: "reForge",
    SUPPORTED_APPS.a1111: "A1111 (or compatible)",
    SUPPORTED_APPS.tests: "Tests",
}


class IFWILDCARDS_CHOICES(Enum):
    ignore = "ignore"
    remove = "remove"
    warn = "warn"
    stop = "stop"


class ONWARNING_CHOICES(Enum):
    warn = "warn"
    stop = "stop"


@dataclass(frozen=True)
class PPPStateOptions:
    """Options that can be set for prompt processing."""

    debug_level: DEBUG_LEVEL = DEBUG_LEVEL.minimal
    on_warning: ONWARNING_CHOICES = ONWARNING_CHOICES.warn
    process_wildcards: bool = True
    keep_choices_order: bool = True
    choice_separator: str = ", "
    if_wildcards: IFWILDCARDS_CHOICES = IFWILDCARDS_CHOICES.stop
    stn_ignore_repeats: bool = True
    stn_separator: str = ", "
    cup_do_cleanup: bool = True  # whether to do cleanup at all (if False, all other cleanup options are ignored)
    cup_cleanup_variables: bool = True
    cup_extra_spaces: bool = True
    cup_empty_constructs: bool = True
    cup_extra_separators: bool = True
    cup_extra_separators2: bool = True
    cup_extra_separators_include_eol: bool = False
    cup_breaks: bool = False
    cup_breaks_eol: bool = False
    cup_ands: bool = False
    cup_ands_eol: bool = False
    cup_extranetwork_tags: bool = False
    cup_merge_attention: bool = True
    cup_remove_extranetwork_tags: bool = False


@dataclass(frozen=True)
class PPPState:
    """State object passed to various PPP components during prompt processing."""

    logger: Logger
    host_config: dict[str, str] = field(default_factory=dict)
    options: PPPStateOptions = field(default_factory=PPPStateOptions)
    system_variables: dict[str, Any] = field(default_factory=dict)
    user_variables: dict[str, Any] = field(default_factory=dict)
    echoed_variables: dict[str, Any] = field(default_factory=dict)
    wildcards_obj: PPPWildcards = field(default_factory=PPPWildcards)
    extranetwork_mappings_obj: PPPExtraNetworkMappings = field(default_factory=PPPExtraNetworkMappings)
    parsers: dict[str, Lark] = field(default_factory=dict)


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


# ------------------- Host configuration -------------------

AttentionOption = Literal["ok", "parentheses", "disable", "remove", "error"]
SchedulingOption = Literal["ok", "before", "after", "first", "remove", "error"]
AlternationOption = Literal["ok", "first", "remove", "error"]
AndOption = Literal["ok", "eol", "comma", "remove", "error"]
BreakOption = Literal["ok", "eol", "comma", "remove", "error"]


class HostConfig(BaseModel):
    """Configuration for a specific host application."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    attention: AttentionOption = "ok"
    scheduling: SchedulingOption = "ok"
    alternation: AlternationOption = "ok"
    and_: AndOption = Field("ok", alias="and")
    break_: BreakOption = Field("ok", alias="break")


# ------------------- Model detection -------------------


class ModelDetectConfig(BaseModel):
    """Detection configuration for a specific host when loading a model."""

    model_config = ConfigDict(populate_by_name=True)

    class_: Optional[list[str]] = Field(None, alias="class")
    property: Optional[str] = None

    @model_validator(mode="after")
    def check_class_or_property(self) -> "ModelDetectConfig":
        if self.class_ is None and self.property is None:
            raise ValueError("either 'class' or 'property' must be specified")
        return self


# ------------------- Variant find_in_filename -------------------


class FindInFilenamePattern(BaseModel):
    """A regex pattern with optional flags used to identify a model variant in the filename."""

    regex: str
    flags: int = 0

    @field_validator("flags", mode="before")
    @classmethod
    def parse_flags(cls, v: object) -> int:
        if isinstance(v, int):
            return v
        if isinstance(v, list):
            flag_value = 0
            for flag in v:
                if not isinstance(flag, str) or not hasattr(re, flag):
                    raise ValueError(f"invalid regex flag '{flag}'")
                flag_value |= getattr(re, flag)
            return flag_value
        raise ValueError(f"expected int or list of flag-name strings, got {type(v).__name__}")

    @model_validator(mode="after")
    def validate_regex(self) -> "FindInFilenamePattern":
        try:
            re.compile(self.regex, self.flags)
        except re.error as exc:
            raise ValueError(f"invalid regex pattern '{self.regex}': {exc}") from exc
        return self


class VariantConfig(BaseModel):
    """Configuration for a specific model variant."""

    find_in_filename: list[FindInFilenamePattern]

    @field_validator("find_in_filename", mode="before")
    @classmethod
    def normalize_find_in_filename(cls, v: object) -> list:
        """Normalize str / dict / list input to always be a list of FindInFilenamePattern-compatible dicts."""
        if isinstance(v, str):
            return [{"regex": v, "flags": re.IGNORECASE}]
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            normalized = []
            for item in v:
                if isinstance(item, str):
                    normalized.append({"regex": item, "flags": re.IGNORECASE})
                elif isinstance(item, dict):
                    normalized.append(item)
                else:
                    raise ValueError(f"expected str or dict in 'find_in_filename' list, got {type(item).__name__}")
            return normalized
        raise ValueError(f"expected str, dict, or list for 'find_in_filename', got {type(v).__name__}")


# ------------------- Model configuration -------------------


class ModelConfig(BaseModel):
    """Configuration for a supported base model."""

    detect: Optional[dict[str, Optional[ModelDetectConfig]]] = None
    variants: Optional[dict[str, VariantConfig]] = None

    @model_validator(mode="after")
    def check_detect_or_variants(self) -> "ModelConfig":
        if self.detect is None and self.variants is None:
            raise ValueError("at least one of 'detect' or 'variants' must be specified")
        return self


# ------------------- Top-level configuration -------------------


class PPPConfig(BaseModel):
    """Top-level PPP configuration structure matching ppp_config.yaml."""

    hosts: Optional[dict[str, Optional[HostConfig]]] = None
    models: Optional[dict[str, Optional[ModelConfig | None]]] = None

    @model_validator(mode="after")
    def check_hosts_or_models(self) -> "PPPConfig":
        if self.hosts is None and self.models is None:
            raise ValueError("at least one of 'hosts' or 'models' must be specified")
        return self
