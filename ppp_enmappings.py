import os
from typing import Optional
import logging
import yaml

from ppp_logging import DEBUG_LEVEL  # pylint: disable=import-error
from ppp_utils import deep_freeze  # pylint: disable=import-error


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
        file (str): The path to the file where the extranetwork mapping is defined.
        variants (list[PPPENMappingVariant]): The processed variants of the extranetwork mapping.
    """

    def __init__(self, fullpath: str, kind: str, name: str, variants: list[dict]):
        self.file: str = fullpath
        self.kind: str = kind
        self.name: str = name
        self.variants: list[PPPENMappingVariant] = [
            PPPENMappingVariant(**{**{"condition": None, "name": None, "parameters": None, "triggers": None, "weight": 1.0}, **v})
            for v in variants
        ]

    def __hash__(self) -> int:
        t = (self.kind, self.name, deep_freeze(self.variants))
        return hash(t)

    def __sizeof__(self):
        return self.kind.__sizeof__() + self.name.__sizeof__() + self.file.__sizeof__() + self.variants.__sizeof__()


class PPPExtraNetworkMappings:
    """
    A class to manage extra network mappings.

    Attributes:
        extranetwork_maps (dict[str, PPPENMapping]): The extra network mappings.
    """

    DEFAULT_ENMAPPINGS_FOLDER = "extranetworkmappings"
    LOCALINPUT_FILENAME = "#INPUT"

    def __init__(self, logger):
        self.__logger: logging.Logger = logger
        self.__debug_level = DEBUG_LEVEL.none
        self.__enmappings_folders = []
        self.__enmappings_files = {}
        self.extranetwork_mappings: dict[str, PPPENMapping] = {}

    def __hash__(self) -> int:
        return hash(deep_freeze(self.extranetwork_mappings))

    def __sizeof__(self):
        return (
            self.extranetwork_mappings.__sizeof__() + self.__enmappings_folders.__sizeof__() + self.__enmappings_files.__sizeof__()
        )

    def refresh_extranetwork_mappings(
        self, debug_level: DEBUG_LEVEL, enmappings_folders: Optional[list[str]], enmappings_input: str = None
    ):
        """
        Initialize the extra network mappings.
        """
        self.__debug_level = debug_level
        self.__enmappings_folders = enmappings_folders or []
        # if self.__debug_level != DEBUG_LEVEL.none:
        #     self.__logger.info("Refreshing extra network mappings...")
        # t1 = time.monotonic_ns()
        for fullpath in list(self.__enmappings_files.keys()):
            if fullpath != self.LOCALINPUT_FILENAME:
                path = os.path.dirname(fullpath)
                if not os.path.exists(fullpath) or not any(
                    os.path.commonpath([path, folder]) == folder for folder in self.__enmappings_folders
                ):
                    self.__remove_extranetwork_mappings_from_path(fullpath)
            elif enmappings_input is None:
                self.__remove_extranetwork_mappings_from_path(fullpath)
        if enmappings_folders is not None or enmappings_input is not None:
            if enmappings_folders is not None:
                for f in self.__enmappings_folders:
                    self.__get_extranetwork_mappings_in_directory(f)
            if enmappings_input is not None:
                self.__get_extranetwork_mappings_in_input(enmappings_input)
        else:
            self.extranetwork_mappings = {}
            self.__enmappings_files = {}
        # t2 = time.monotonic_ns()
        # if self.__debug_level != DEBUG_LEVEL.none:
        #     self.__logger.info(f"Extra network mappings refresh time: {(t2 - t1) / 1_000_000_000:.3f} seconds")

    # def get_extranetwork_mappings(self, key: str) -> list[PPPENMapping]:
    #     """
    #     Get all extra network mappings that match a key.
    #
    #     Args:
    #         key (str): The key to match (kind:name).
    #
    #     Returns:
    #         list: A list of all extra network mappings that match the key.
    #     """
    #     keys = sorted(fnmatch.filter(self.extranetwork_mappings.keys(), key))
    #     return [self.extranetwork_mappings[k] for k in keys]

    def __remove_extranetwork_mappings_from_path(self, full_path: str, debug=True):
        """
        Clear all extra network mappings in a file.

        Args:
            full_path (str): The path to the file.
            debug (bool): Whether to print debug messages or not.
        """
        last_modified_cached = self.__enmappings_files.get(full_path, None)  # a time or a hash
        if debug and last_modified_cached is not None and self.__debug_level != DEBUG_LEVEL.none:
            if full_path == self.LOCALINPUT_FILENAME:
                self.__logger.debug("Removing extra network mappings from input")
            else:
                self.__logger.debug(f"Removing extra network mappings from file: {full_path}")
        if full_path in self.__enmappings_files.keys():
            del self.__enmappings_files[full_path]
        for key in list(self.extranetwork_mappings.keys()):
            if self.extranetwork_mappings[key].file == full_path:
                del self.extranetwork_mappings[key]

    def __get_extranetwork_mappings_in_file(self, full_path: str):
        """
        Get all extra network mappings in a file.

        Args:
            full_path (str): The path to the file.
        """
        last_modified = os.path.getmtime(full_path)
        last_modified_cached = self.__enmappings_files.get(full_path, None)
        if last_modified_cached is not None and last_modified == self.__enmappings_files[full_path]:
            return
        filename = os.path.basename(full_path)
        _, extension = os.path.splitext(filename)
        if extension not in (".yaml", ".yml", ".json"):
            return
        self.__remove_extranetwork_mappings_from_path(full_path, False)
        if last_modified_cached is not None and self.__debug_level != DEBUG_LEVEL.none:
            self.__logger.debug(f"Updating extra network mappings from file: {full_path}")
        self.__get_extranetwork_mappings_in_structured_file(full_path)
        self.__enmappings_files[full_path] = last_modified

    def __get_extranetwork_mappings_in_input(self, enmappings_input: str):
        """
        Get all extra network mappings in the string.

        Args:
            enmappings_input (str): The input string containing extra network mappings in yaml format.
        """
        new_h = hash(enmappings_input)
        h = self.__enmappings_files.get(self.LOCALINPUT_FILENAME, None)
        if h == new_h:
            return
        self.__remove_extranetwork_mappings_from_path(self.LOCALINPUT_FILENAME, False)
        if h is not None and self.__debug_level != DEBUG_LEVEL.none:
            self.__logger.debug("Updating extra network mappings from input")
        enmappings_input = enmappings_input.strip()
        if enmappings_input != "":
            try:
                content = yaml.safe_load(enmappings_input)
            except yaml.YAMLError as e:
                self.__logger.warning(f"Invalid format for input extra network mappings: {e}")
                return
            if content is not None:
                self.__add_extranetwork_mapping(content, self.LOCALINPUT_FILENAME)
        self.__enmappings_files[self.LOCALINPUT_FILENAME] = new_h

    def __add_extranetwork_mapping(self, content: dict[str, dict[str, list[dict]]], full_path: str):
        """
        Add an extra network mapping to the extra network mappings dictionary.

        Args:
            content (object): The content of the extra network mapping.
            full_path (str): The path to the file that contains it.
        """
        if not isinstance(content, dict):
            self.__logger.warning(f"Invalid extra network mapping in file '{full_path}'!")
            return
        for kind, maps in content.items():
            if not isinstance(maps, dict):
                self.__logger.warning(f"Invalid extra network mapping definition for '{kind}:*' in file '{full_path}'!")
            else:
                for name, variants in maps.items():
                    key = f"{kind}:{name}"
                    if not isinstance(variants, list):
                        self.__logger.warning(
                            f"Invalid extra network mapping definition for '{key}' in file '{full_path}'!"
                        )
                    elif self.extranetwork_mappings.get(key, None) is not None:
                        self.__logger.warning(
                            f"Duplicate extra network mapping '{key}' in file '{full_path}' and '{self.extranetwork_mappings[key].file}'!"
                        )
                    elif not isinstance(variants, list) or not all(isinstance(v, dict) for v in variants):
                        self.__logger.warning(
                            f"Invalid extra network mapping definition for '{key}' in file '{full_path}'!"
                        )
                    else:
                        self.extranetwork_mappings[key] = PPPENMapping(full_path, kind, name, variants)

    def __get_extranetwork_mappings_in_structured_file(self, full_path):
        """
        Get all extra network mappings in a structured file.

        Args:
            full_path (str): The path to the file.
            base (str): The base path for the extra network mappings.
        """
        with open(full_path, "r", encoding="utf-8") as file:
            content = yaml.safe_load(file)
        self.__add_extranetwork_mapping(content, full_path)

    def __get_extranetwork_mappings_in_directory(self, directory: str):
        """
        Get all extra network mappings in a directory.

        Args:
            directory (str): The path to the directory.
        """
        if not os.path.exists(directory):
            self.__logger.warning(f"Extra network mappings directory '{directory}' does not exist!")
            return
        for filename in os.listdir(directory):
            full_path = os.path.abspath(os.path.join(directory, filename))
            if os.path.basename(full_path).startswith("."):
                continue
            if os.path.isdir(full_path):
                self.__get_extranetwork_mappings_in_directory(full_path)
            elif os.path.isfile(full_path):
                self.__get_extranetwork_mappings_in_file(full_path)
