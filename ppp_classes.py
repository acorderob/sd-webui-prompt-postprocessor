"""Pydantic models for the PPP configuration file structure (ppp_config.yaml)."""

import re
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
