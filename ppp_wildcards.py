import fnmatch
import os
import json
from typing import Optional
import logging
import yaml

from ppp_logging import DEBUG_LEVEL


class PPPWildcard:

    def __init__(self, fullpath: str, key: str, choices: list[str]):
        self.key: str = key
        self.file: str = fullpath
        self.unprocessed_choices: list[str] = choices
        self.choices: list[dict] = None
        self.options: dict = None


class PPPWildcards:

    DEFAULT_WILDCARDS_FOLDER = "wildcards"

    def __init__(self, logger):
        self.logger: logging.Logger = logger
        self.debug_level = DEBUG_LEVEL.none
        self.wildcards_folders = []
        self.wildcards: dict[str, PPPWildcard] = {}
        self.wildcard_files = {}

    def refresh_wildcards(self, debug_level: DEBUG_LEVEL, wildcards_folders: Optional[list[str]]):
        """
        Initialize the wildcards.
        """
        self.debug_level = debug_level
        self.wildcards_folders = wildcards_folders
        if wildcards_folders is not None:
            # if self.debug_level != DEBUG_LEVEL.none:
            #     self.logger.info("Initializing wildcards...")
            # t1 = time.time()
            for fullpath in list(self.wildcard_files.keys()):
                path = os.path.dirname(fullpath)
                if not os.path.exists(fullpath) or not any(
                    os.path.commonpath([path, folder]) == folder for folder in self.wildcards_folders
                ):
                    self.__remove_wildcards_from_file(fullpath)
            for f in self.wildcards_folders:
                self.__get_wildcards_in_directory(f, f)
            # t2 = time.time()
            # if self.debug_level != DEBUG_LEVEL.none:
            #     self.logger.info(f"Wildcards init time: {t2 - t1:.3f} seconds")
        else:
            self.wildcards_folders = []
            self.wildcards = {}
            self.wildcard_files = {}

    def get_wildcards(self, key: str) -> list[PPPWildcard]:
        keys = sorted(fnmatch.filter(self.wildcards.keys(), key))
        return [self.wildcards[k] for k in keys]

    def __get_keys_in_dict(self, dictionary: dict, prefix="") -> list[str]:
        """
        Get all keys in a dictionary.

        Args:
            dictionary (dict): The dictionary to check.
            prefix (str): The prefix for the current key.

        Returns:
            list: A list of all keys in the dictionary, including nested keys.
        """
        keys = []
        for key in dictionary.keys():
            if isinstance(dictionary[key], dict):
                keys.extend(self.__get_keys_in_dict(dictionary[key], prefix + key + "/"))
            else:
                keys.append(prefix + str(key))
        return keys

    def __get_nested(self, dictionary: dict, keys: str) -> object:
        """
        Get a nested value from a dictionary.

        Args:
            dictionary (dict): The dictionary to check.
            keys (str): The keys to get the value from.

        Returns:
            object: The value of the nested keys in the dictionary.
        """
        keys = keys.split("/")
        current_dict = dictionary
        for key in keys:
            current_dict = current_dict.get(key)
            if current_dict is None:
                return None
        return current_dict

    def __remove_wildcards_from_file(self, full_path: str, debug=True):
        """
        Clear all wildcards in a file.

        Args:
            full_path (str): The path to the file.
            debug (bool): Whether to print debug messages or not.
        """
        last_modified_cached = self.wildcard_files.get(full_path, None)
        if debug and last_modified_cached is not None and self.debug_level != DEBUG_LEVEL.none:
            self.logger.debug(f"Removing wildcards from file: {full_path}")
        if full_path in self.wildcard_files.keys():
            del self.wildcard_files[full_path]
        for key in list(self.wildcards.keys()):
            if self.wildcards[key].file == full_path:
                del self.wildcards[key]

    def __get_wildcards_in_file(self, base, full_path: str):
        """
        Get all wildcards in a file.

        Args:
            base (str): The base path for the wildcards.
            full_path (str): The path to the file.
        """
        last_modified = os.path.getmtime(full_path)
        last_modified_cached = self.wildcard_files.get(full_path, None)
        if last_modified_cached is not None and last_modified == self.wildcard_files[full_path]:
            return
        filename = os.path.basename(full_path)
        _, extension = os.path.splitext(filename)
        if extension not in (".txt", ".json", ".yaml", ".yml"):
            return
        self.__remove_wildcards_from_file(full_path, False)
        if last_modified_cached is not None and self.debug_level != DEBUG_LEVEL.none:
            self.logger.debug(f"Updating wildcards from file: {full_path}")
        if extension == ".txt":
            self.__get_wildcards_in_text_file(full_path, base)
        elif extension in (".json", ".yaml", ".yml"):
            self.__get_wildcards_in_structured_file(full_path, base)
        self.wildcard_files[full_path] = last_modified

    def __get_choices(self, obj: object) -> list[dict]:
        choices = None
        if obj is not None:
            if isinstance(obj, (str, dict)):
                choices = [obj]
            elif isinstance(obj, (int, float, bool)):
                choices = [str(obj)]
            elif isinstance(obj, list) and len(obj) > 0:
                choices = []
                for c in obj:
                    if isinstance(c, (str, dict)):
                        choices.append(c)
                    elif isinstance(c, (int, float, bool)):
                        choices.append(str(c))
        return choices

    def __get_wildcards_in_structured_file(self, full_path, base):
        external_key: str = os.path.relpath(os.path.splitext(full_path)[0], base)
        external_key_parts = external_key.split(os.sep)
        _, extension = os.path.splitext(full_path)
        with open(full_path, "r", encoding="utf-8") as file:
            if extension == ".json":
                content = json.loads(file.read())
            else:
                content = yaml.safe_load(file)
        if isinstance(content, dict):
            external_key_parts = external_key_parts[:-1]
            keys = self.__get_keys_in_dict(content)
            for key in keys:
                fullkey = "/".join(external_key_parts + [key])
                if self.wildcards.get(fullkey, None) is not None:
                    self.logger.warning(
                        f"Duplicate wildcard '{fullkey}' in file '{full_path}' and '{self.wildcards[fullkey].file}'!"
                    )
                else:
                    obj = self.__get_nested(content, key)
                    choices = self.__get_choices(obj)
                    if choices is None:
                        self.logger.warning(f"Invalid wildcard '{fullkey}' in file '{full_path}'!")
                    else:
                        self.wildcards[fullkey] = PPPWildcard(full_path, fullkey, choices)
            return
        if isinstance(content, str):
            content = [content]
        elif isinstance(content, (int, float, bool)):
            content = [str(content)]
        if not isinstance(content, list):
            self.logger.warning(f"Invalid wildcard in file '{full_path}'!")
            return
        fullkey = "/".join(external_key_parts)
        if self.wildcards.get(fullkey, None) is not None:
            self.logger.warning(
                f"Duplicate wildcard '{fullkey}' in file '{full_path}' and '{self.wildcards[fullkey].file}'!"
            )
        else:
            choices = self.__get_choices(content)
            if choices is None:
                self.logger.warning(f"Invalid wildcard '{fullkey}' in file '{full_path}'!")
            else:
                self.wildcards[fullkey] = PPPWildcard(full_path, fullkey, choices)

    def __get_wildcards_in_text_file(self, full_path, base):
        external_key: str = os.path.relpath(os.path.splitext(full_path)[0], base)
        external_key_parts = external_key.split(os.sep)
        with open(full_path, "r", encoding="utf-8") as file:
            text_content = map(lambda x: x.strip("\n\r"), file.readlines())
        text_content = list(filter(lambda x: x.strip() != "" and not x.strip().startswith("#"), text_content))
        text_content = [x.split("#")[0].rstrip() if len(x.split("#")) > 1 else x for x in text_content]
        fullkey = "/".join(external_key_parts)
        if self.wildcards.get(fullkey, None) is not None:
            self.logger.warning(
                f"Duplicate wildcard '{fullkey}' in file '{full_path}' and '{self.wildcards[fullkey].file}'!"
            )
        else:
            if len(text_content) == 0:
                self.logger.warning(f"Invalid wildcard in file '{full_path}'!")
            else:
                self.wildcards[fullkey] = PPPWildcard(full_path, fullkey, text_content)

    def __get_wildcards_in_directory(self, base: str, directory: str):
        """
        Get all wildcards in a directory.

        Args:
            base (str): The base path for the wildcards.
            directory (str): The path to the directory.
        """
        if not os.path.exists(directory):
            self.logger.warning(f"Wildcard directory '{directory}' does not exist!")
            return
        for filename in os.listdir(directory):
            full_path = os.path.abspath(os.path.join(directory, filename))
            if os.path.basename(full_path).startswith("."):
                continue
            if os.path.isdir(full_path):
                self.__get_wildcards_in_directory(base, full_path)
            elif os.path.isfile(full_path):
                self.__get_wildcards_in_file(base, full_path)
