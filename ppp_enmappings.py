from pathlib import Path
from typing import Optional
import logging
import yaml

from ppp_logging import DEBUG_LEVEL, log
from ppp_utils import deep_freeze, escape_single_quotes


class PPPENMappingVariant:
    """
    A class to represent a variant of an extra network mapping.

    Attributes:
        condition (str): The condition for the variant.
        name (str): The name of the variant.
        parameters (float|str): The parameters for the variant.
        triggers (list[str]): The triggers for the variant.
        weight (float): The weight for the variant when multiple variants apply.
    """

    def __init__(self, condition: str, name: str, parameters: float | str, triggers: list[str], weight: float):
        self.condition: str = condition
        self.name: str = name
        self.parameters: float | str = parameters
        self.triggers: list[str] = triggers
        self.weight: float = weight


class PPPENMapping:
    """
    A extra network mapping object.

    Attributes:
        kind (str): The kind of the extra network.
        name (str): The name of the extra network mapping.
        file (Path | None): The path to the file where the extranetwork mapping is defined, or None if from inline input.
        variants (list[PPPENMappingVariant]): The processed variants of the extranetwork mapping.
    """

    def __init__(self, fullpath: Path | None, kind: str, name: str, variants: list[dict]):
        self.file: Path | None = fullpath
        self.kind: str = kind
        self.name: str = name
        self.variants: list[PPPENMappingVariant] = [
            PPPENMappingVariant(
                **{**{"condition": None, "name": None, "parameters": None, "triggers": None, "weight": 1.0}, **v}
            )
            for v in variants
        ]

    def __hash__(self) -> int:
        t = (self.kind, self.name, deep_freeze(self.variants))
        return hash(t)

    def __sizeof__(self):
        return (
            self.kind.__sizeof__()
            + self.name.__sizeof__()
            + (self.file.__sizeof__() if self.file is not None else 0)
            + self.variants.__sizeof__()
        )


class PPPExtraNetworkMappings:
    """
    A class to manage extra network mappings.

    Attributes:
        extranetwork_maps (dict[str, PPPENMapping]): The extra network mappings.
    """

    DEFAULT_ENMAPPINGS_FOLDER = "extranetworkmappings"

    def __init__(self, logger=None):
        self.__logger: logging.Logger = logger
        self.__debug_level = DEBUG_LEVEL.none
        self.__enmappings_folders: list[Path] = []
        self.__enmappings_files: dict[Path, float] = {}
        self.__local_enmappings_input_hash: int | None = None
        self.extranetwork_mappings: dict[str, PPPENMapping] = {}
        self.cached_mappings = {}

    def __hash__(self) -> int:
        return hash(deep_freeze(self.extranetwork_mappings))

    def __sizeof__(self):
        return (
            self.extranetwork_mappings.__sizeof__()
            + self.__enmappings_folders.__sizeof__()
            + self.__enmappings_files.__sizeof__()
            + self.cached_mappings.__sizeof__()
        )

    def refresh_extranetwork_mappings(
        self,
        debug_level: DEBUG_LEVEL,
        enmappings_folders: Optional[list[Path]],
        enmappings_input: str = None,
    ):
        """
        Initialize the extra network mappings.
        """
        self.__debug_level = debug_level
        self.__enmappings_folders = [Path(f) for f in (enmappings_folders or [])]
        # log(self.__logger, self.__debug_level, logging.INFO, "Refreshing extra network mappings...")
        # t1 = time.monotonic_ns()
        self.cached_mappings = {}
        for fullpath in list(self.__enmappings_files.keys()):
            if not fullpath.exists() or not any(
                fullpath.parent.is_relative_to(folder) for folder in self.__enmappings_folders
            ):
                self.__remove_extranetwork_mappings_from_path(fullpath)
        if enmappings_input is None and self.__local_enmappings_input_hash is not None:
            self.__remove_extranetwork_mappings_from_input()
        if enmappings_folders is not None or enmappings_input is not None:
            if enmappings_folders is not None:
                for f in self.__enmappings_folders:
                    self.__get_extranetwork_mappings_in_path(f)
            if enmappings_input is not None:
                self.__get_extranetwork_mappings_in_input(enmappings_input)
        else:
            self.extranetwork_mappings = {}
            self.__enmappings_files = {}
            self.__local_enmappings_input_hash = None
        # t2 = time.monotonic_ns()
        # log(self.__logger, self.__debug_level, logging.INFO, f"Extra network mappings refresh time: {(t2 - t1) / 1_000_000_000:.3f} seconds")

    def __remove_extranetwork_mappings_from_path(self, full_path: Path, debug=True):
        """
        Clear all extra network mappings from a file.

        Args:
            full_path (Path): The path to the file.
            debug (bool): Whether to print debug messages or not.
        """
        if debug and full_path in self.__enmappings_files:
            log(
                self.__logger,
                self.__debug_level,
                logging.DEBUG,
                f"Removing extra network mappings from file: {full_path}",
            )
        if full_path in self.__enmappings_files:
            del self.__enmappings_files[full_path]
        for key in list(self.extranetwork_mappings.keys()):
            if self.extranetwork_mappings[key].file == full_path:
                del self.extranetwork_mappings[key]

    def __remove_extranetwork_mappings_from_input(self, debug=True):
        """
        Clear all extra network mappings loaded from inline input.

        Args:
            debug (bool): Whether to print debug messages or not.
        """
        if debug and self.__local_enmappings_input_hash is not None:
            log(self.__logger, self.__debug_level, logging.DEBUG, "Removing extra network mappings from input")
        self.__local_enmappings_input_hash = None
        for key in list(self.extranetwork_mappings.keys()):
            if self.extranetwork_mappings[key].file is None:
                del self.extranetwork_mappings[key]

    def __get_extranetwork_mappings_in_file(self, full_path: Path):
        """
        Get all extra network mappings in a file.

        Args:
            full_path (Path): The path to the file.
        """
        last_modified = full_path.stat().st_mtime
        last_modified_cached = self.__enmappings_files.get(full_path, None)
        if last_modified_cached is not None and last_modified == self.__enmappings_files[full_path]:
            return
        extension = full_path.suffix
        if extension not in (".yaml", ".yml", ".json"):
            return
        self.__remove_extranetwork_mappings_from_path(full_path, False)
        if last_modified_cached is not None:
            log(
                self.__logger,
                self.__debug_level,
                logging.DEBUG,
                f"Updating extra network mappings from file: {full_path}",
            )
        self.__get_extranetwork_mappings_in_structured_file(full_path)
        self.__enmappings_files[full_path] = last_modified

    def __get_extranetwork_mappings_in_input(self, enmappings_input: str):
        """
        Get all extra network mappings in the string.

        Args:
            enmappings_input (str): The input string containing extra network mappings in yaml format.
        """
        new_h = hash(enmappings_input)
        if new_h == self.__local_enmappings_input_hash:
            return
        was_loaded = self.__local_enmappings_input_hash is not None
        self.__remove_extranetwork_mappings_from_input(False)
        if was_loaded:
            log(self.__logger, self.__debug_level, logging.DEBUG, "Updating extra network mappings from input")
        enmappings_input = enmappings_input.strip()
        if enmappings_input != "":
            try:
                content = yaml.safe_load(enmappings_input)
            except yaml.YAMLError as e:
                log(
                    self.__logger,
                    self.__debug_level,
                    logging.WARNING,
                    f"Invalid format for input extra network mappings: {e}",
                )
                return
            if content is not None:
                self.__add_extranetwork_mapping(content, None)
        self.__local_enmappings_input_hash = new_h

    def __add_extranetwork_mapping(self, content: dict[str, dict[str, list[dict]]], full_path: Path | None):
        """
        Add an extra network mapping to the extra network mappings dictionary.

        Args:
            content (object): The content of the extra network mapping.
            full_path (Path | None): The path to the file that contains it, or None if from inline input.
        """
        file_str = str(full_path) if full_path is not None else "input"
        if not isinstance(content, dict):
            log(
                self.__logger,
                self.__debug_level,
                logging.WARNING,
                f"Invalid extra network mapping in file '{escape_single_quotes(file_str)}'!",
            )
            return
        for kind, maps in content.items():
            if not isinstance(maps, dict):
                log(
                    self.__logger,
                    self.__debug_level,
                    logging.WARNING,
                    f"Invalid extra network mapping definition for '{escape_single_quotes(kind)}:*' in file '{escape_single_quotes(file_str)}'!",
                )
            else:
                for name, variants in maps.items():
                    key = f"{kind}:{name}"
                    if not isinstance(variants, list):
                        log(
                            self.__logger,
                            self.__debug_level,
                            logging.WARNING,
                            f"Invalid extra network mapping definition for '{escape_single_quotes(key)}' in file '{escape_single_quotes(file_str)}'!",
                        )
                    elif self.extranetwork_mappings.get(key, None) is not None:
                        f = (
                            str(self.extranetwork_mappings[key].file)
                            if self.extranetwork_mappings[key].file is not None
                            else "input"
                        )
                        log(
                            self.__logger,
                            self.__debug_level,
                            logging.WARNING,
                            f"Duplicate extra network mapping '{escape_single_quotes(key)}' in file '{escape_single_quotes(file_str)}' and '{escape_single_quotes(f)}'!",
                        )
                    elif not isinstance(variants, list) or not all(isinstance(v, dict) for v in variants):
                        log(
                            self.__logger,
                            self.__debug_level,
                            logging.WARNING,
                            f"Invalid extra network mapping definition for '{escape_single_quotes(key)}' in file '{escape_single_quotes(file_str)}'!",
                        )
                    else:
                        self.extranetwork_mappings[key] = PPPENMapping(full_path, kind, name, variants)

    def __get_extranetwork_mappings_in_structured_file(self, full_path: Path):
        """
        Get all extra network mappings in a structured file.

        Args:
            full_path (Path): The path to the file.
        """
        try:
            try:
                with open(full_path, "r", encoding="utf-8") as file:
                    content = yaml.safe_load(file)
            except:  # pylint: disable=bare-except
                log(
                    self.__logger,
                    self.__debug_level,
                    logging.WARNING,
                    f"Could not read file '{escape_single_quotes(str(full_path))}' with utf-8 encoding, trying windows-1252...",
                )
                with open(full_path, "r", encoding="windows-1252") as file:
                    content = yaml.safe_load(file)
            self.__add_extranetwork_mapping(content, full_path)
        except Exception as e:  # pylint: disable=broad-except
            log(
                self.__logger,
                self.__debug_level,
                logging.ERROR,
                f"Error reading extra network mappings from file '{escape_single_quotes(str(full_path))}': {e}",
            )

    def __get_extranetwork_mappings_in_path(self, path: Path):
        """
        Get all extra network mappings in a path.

        Args:
            path (Path): The path (folder or file).
        """
        if not path.exists():
            log(
                self.__logger,
                self.__debug_level,
                logging.WARNING,
                f"Extra network mappings path '{escape_single_quotes(str(path))}' does not exist!",
            )
            return
        if path.is_file():
            self.__get_extranetwork_mappings_in_file(path)
            return
        for child in path.iterdir():
            if child.name.startswith("."):
                continue
            self.__get_extranetwork_mappings_in_path(child)
