import fnmatch
import os
from typing import Optional
import logging
import yaml

from ppp_logging import DEBUG_LEVEL  # pylint: disable=import-error


def deep_freeze(obj):
    """
    Deep freeze an object.

    Args:
        obj (object): The object to freeze.

    Returns:
        object: The frozen object.
    """
    if isinstance(obj, dict):
        return tuple((k, deep_freeze(v)) for k, v in sorted(obj.items()))
    if isinstance(obj, list):
        return tuple(deep_freeze(i) for i in obj)
    if isinstance(obj, set):
        return tuple(deep_freeze(i) for i in sorted(obj))
    return obj


class PPPWildcard:
    """
    A wildcard object.

    Attributes:
        key (str): The key of the wildcard.
        file (str): The path to the file where the wildcard is defined.
        unprocessed_choices (list[str]): The unprocessed choices of the wildcard.
        choices (list[dict]): The processed choices of the wildcard.
        options (dict): The options of the wildcard.
    """

    def __init__(self, fullpath: str, key: str, choices: list[str]):
        self.key: str = key
        self.file: str = fullpath
        self.unprocessed_choices: list[str] = choices
        self.choices: list[dict] = None
        self.options: dict = None

    def __hash__(self) -> int:
        t = (self.key, deep_freeze(self.unprocessed_choices))
        return hash(t)

    def __sizeof__(self):
        return (
            self.key.__sizeof__()
            + self.file.__sizeof__()
            + self.unprocessed_choices.__sizeof__()
            + self.choices.__sizeof__()
            + self.options.__sizeof__()
        )


class PPPWildcards:
    """
    A class to manage wildcards.

    Attributes:
        wildcards (dict[str, PPPWildcard]): The wildcards.
    """

    DEFAULT_WILDCARDS_FOLDER = "wildcards"
    LOCALINPUT_FILENAME = "#INPUT"

    def __init__(self, logger):
        self.__logger: logging.Logger = logger
        self.__debug_level = DEBUG_LEVEL.none
        self.__wildcards_folders = []
        self.__wildcard_files = {}
        self.wildcards: dict[str, PPPWildcard] = {}

    def __hash__(self) -> int:
        return hash(deep_freeze(self.wildcards))

    def __sizeof__(self):
        return self.wildcards.__sizeof__() + self.__wildcards_folders.__sizeof__() + self.__wildcard_files.__sizeof__()

    def refresh_wildcards(
        self, debug_level: DEBUG_LEVEL, wildcards_folders: Optional[list[str]], wildcards_input: str = None
    ):
        """
        Initialize the wildcards.
        """
        self.__debug_level = debug_level
        self.__wildcards_folders = wildcards_folders or []
        # if self.__debug_level != DEBUG_LEVEL.none:
        #     self.__logger.info("Refreshing wildcards...")
        # t1 = time.time()
        for fullpath in list(self.__wildcard_files.keys()):
            if fullpath != self.LOCALINPUT_FILENAME:
                path = os.path.dirname(fullpath)
                if not os.path.exists(fullpath) or not any(
                    os.path.commonpath([path, folder]) == folder for folder in self.__wildcards_folders
                ):
                    self.__remove_wildcards_from_path(fullpath)
            elif wildcards_input is None:
                self.__remove_wildcards_from_path(fullpath)
        if wildcards_folders is not None or wildcards_input is not None:
            if wildcards_folders is not None:
                for f in self.__wildcards_folders:
                    self.__get_wildcards_in_directory(f, f)
            if wildcards_input is not None:
                self.__get_wildcards_in_input(wildcards_input)
        else:
            self.wildcards = {}
            self.__wildcard_files = {}
        # t2 = time.time()
        # if self.__debug_level != DEBUG_LEVEL.none:
        #     self.__logger.info(f"Wildcards refresh time: {t2 - t1:.3f} seconds")

    def get_wildcards(self, key: str) -> list[PPPWildcard]:
        """
        Get all wildcards that match a key.

        Args:
            key (str): The key to match.

        Returns:
            list: A list of all wildcards that match the key.
        """
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

    def __remove_wildcards_from_path(self, full_path: str, debug=True):
        """
        Clear all wildcards in a file.

        Args:
            full_path (str): The path to the file.
            debug (bool): Whether to print debug messages or not.
        """
        last_modified_cached = self.__wildcard_files.get(full_path, None)  # a time or a hash
        if debug and last_modified_cached is not None and self.__debug_level != DEBUG_LEVEL.none:
            if full_path == self.LOCALINPUT_FILENAME:
                self.__logger.debug("Removing wildcards from input")
            else:
                self.__logger.debug(f"Removing wildcards from file: {full_path}")
        if full_path in self.__wildcard_files.keys():
            del self.__wildcard_files[full_path]
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
        last_modified_cached = self.__wildcard_files.get(full_path, None)
        if last_modified_cached is not None and last_modified == self.__wildcard_files[full_path]:
            return
        filename = os.path.basename(full_path)
        _, extension = os.path.splitext(filename)
        if extension not in (".txt", ".json", ".yaml", ".yml"):
            return
        self.__remove_wildcards_from_path(full_path, False)
        if last_modified_cached is not None and self.__debug_level != DEBUG_LEVEL.none:
            self.__logger.debug(f"Updating wildcards from file: {full_path}")
        if extension == ".txt":
            self.__get_wildcards_in_text_file(full_path, base)
        elif extension in (".json", ".yaml", ".yml"):
            self.__get_wildcards_in_structured_file(full_path, base)
        self.__wildcard_files[full_path] = last_modified

    def __get_wildcards_in_input(self, wildcards_input: str):
        """
        Get all wildcards in the string.

        Args:
            wildcards_input (str): The input string containing wildcards in json or yaml format.
        """
        new_h = hash(wildcards_input)
        h = self.__wildcard_files.get(self.LOCALINPUT_FILENAME, None)
        if h == new_h:
            return
        self.__remove_wildcards_from_path(self.LOCALINPUT_FILENAME, False)
        if h is not None and self.__debug_level != DEBUG_LEVEL.none:
            self.__logger.debug("Updating wildcards from input")
        wildcards_input = wildcards_input.strip()
        if wildcards_input != "":
            try:
                content = yaml.safe_load(wildcards_input)
            except yaml.YAMLError as e:
                self.__logger.warning(f"Invalid format for input wildcards: {e}")
                return
            if content is not None:
                self.__add_wildcard(content, self.LOCALINPUT_FILENAME, [self.LOCALINPUT_FILENAME])
        self.__wildcard_files[self.LOCALINPUT_FILENAME] = new_h

    def is_dict_choices_options(self, d: dict) -> bool:
        """
        Check if a dictionary is a valid choices options dictionary.

        Args:
            d (dict): The dictionary to check.

        Returns:
            bool: Whether the dictionary is a valid choices options dictionary or not.
        """
        return all(
            k in ["sampler", "repeating", "count", "from", "to", "prefix", "suffix", "separator"] for k in d.keys()
        )

    def is_dict_choice_options(self, d: dict) -> bool:
        """
        Check if a dictionary is a valid choice options dictionary.

        Args:
            d (dict): The dictionary to check.

        Returns:
            bool: Whether the dictionary is a valid choice options dictionary or not.
        """
        return all(k in ["labels", "weight", "if", "content", "text"] for k in d.keys())

    def __get_choices(self, obj: object, full_path: str, key_parts: list[str]) -> list:
        """
        We process the choices in the object and return them as a list.

        Args:
            obj (object): the value of a wildcard
            full_path (str): path to the file where the wildcard is defined
            key_parts (list[str]): parts of the key for the wildcard

        Returns:
            list: list of choices
        """
        if obj is None:
            return None
        if isinstance(obj, (str, dict)):
            return [obj]
        if isinstance(obj, (int, float, bool)):
            return [str(obj)]
        if not isinstance(obj, list) or len(obj) == 0:
            self.__logger.warning(f"Invalid format in wildcard '{'/'.join(key_parts)}' in file '{full_path}'!")
            return None
        choices = []
        for i, c in enumerate(obj):
            if isinstance(c, (str, int, float, bool)):
                choices.append(str(c))
            elif isinstance(c, list):
                # we create an anonymous wildcard
                choices.append(self.__create_anonymous_wildcard(full_path, key_parts, i, c))
            elif isinstance(c, dict):
                choices.append(self.__process_dict_choice(c, full_path, key_parts, i))
            else:
                self.__logger.warning(
                    f"Invalid choice {i+1} in wildcard '{'/'.join(key_parts)}' in file '{full_path}'!"
                )
        return choices

    def __process_dict_choice(self, c: dict, full_path: str, key_parts: list[str], i: int) -> dict:
        """
        Process a dictionary choice.

        Args:
            c (dict): The dictionary choice.
            full_path (str): The path to the file.
            key_parts (list[str]): The parts of the key.
            i (int): The index of the choice.

        Returns:
            dict: The processed choice.
        """
        if self.is_dict_choices_options(c) or self.is_dict_choice_options(c):
            # we assume it is a choice or wildcard parameters in object format
            choice = c
            choice_content = choice.get("content", choice.get("text", None))
            if choice_content is not None and isinstance(choice_content, list):
                # we create an anonymous wildcard
                choice["content"] = self.__create_anonymous_wildcard(full_path, key_parts, i, choice_content)
                if "text" in choice:
                    del choice["text"]
            return choice
        if len(c) == 1:
            # we assume it is an anonymous wildcard with options
            firstkey = list(c.keys())[0]
            return self.__create_anonymous_wildcard(full_path, key_parts, i, c[firstkey], firstkey)
        self.__logger.warning(f"Invalid choice {i+1} in wildcard '{'/'.join(key_parts)}' in file '{full_path}'!")
        return None

    def __create_anonymous_wildcard(self, full_path, key_parts, i, content, options=None):
        """
        Create an anonymous wildcard.

        Args:
            full_path (str): The path to the file that contains it.
            key_parts (list[str]): The parts of the key.
            i (int): The index of the wildcard.
            content (object): The content of the wildcard.
            options (str): The options for the choice where the wildcard is defined.

        Returns:
            str: The resulting value for the choice.
        """
        new_parts = key_parts + [f"#ANON_{i}"]
        self.__add_wildcard(content, full_path, new_parts)
        value = f"__{'/'.join(new_parts)}__"
        if options is not None:
            value = f"{options}::{value}"
        return value

    def __add_wildcard(self, content: object, full_path: str, external_key_parts: list[str]):
        """
        Add a wildcard to the wildcards dictionary.

        Args:
            content (object): The content of the wildcard.
            full_path (str): The path to the file that contains it.
            external_key_parts (list[str]): The parts of the key.
        """
        key_parts = external_key_parts.copy()
        if isinstance(content, dict):
            key_parts.pop()
            keys = self.__get_keys_in_dict(content)
            for key in keys:
                tmp_key_parts = key_parts.copy()
                tmp_key_parts.extend(key.split("/"))
                fullkey = "/".join(tmp_key_parts)
                if self.wildcards.get(fullkey, None) is not None:
                    self.__logger.warning(
                        f"Duplicate wildcard '{fullkey}' in file '{full_path}' and '{self.wildcards[fullkey].file}'!"
                    )
                else:
                    obj = self.__get_nested(content, key)
                    choices = self.__get_choices(obj, full_path, tmp_key_parts)
                    if choices is None:
                        self.__logger.warning(f"Invalid wildcard '{fullkey}' in file '{full_path}'!")
                    else:
                        self.wildcards[fullkey] = PPPWildcard(full_path, fullkey, choices)
            return
        if isinstance(content, str):
            content = [content]
        elif isinstance(content, (int, float, bool)):
            content = [str(content)]
        if not isinstance(content, list):
            self.__logger.warning(f"Invalid wildcard in file '{full_path}'!")
            return
        fullkey = "/".join(key_parts)
        if self.wildcards.get(fullkey, None) is not None:
            self.__logger.warning(
                f"Duplicate wildcard '{fullkey}' in file '{full_path}' and '{self.wildcards[fullkey].file}'!"
            )
        else:
            choices = self.__get_choices(content, full_path, key_parts)
            if choices is None:
                self.__logger.warning(f"Invalid wildcard '{fullkey}' in file '{full_path}'!")
            else:
                self.wildcards[fullkey] = PPPWildcard(full_path, fullkey, choices)

    def __get_wildcards_in_structured_file(self, full_path, base):
        """
        Get all wildcards in a structured file.

        Args:
            full_path (str): The path to the file.
            base (str): The base path for the wildcards.
        """
        external_key: str = os.path.relpath(os.path.splitext(full_path)[0], base)
        external_key_parts = external_key.split(os.sep)
        with open(full_path, "r", encoding="utf-8") as file:
            content = yaml.safe_load(file)
        self.__add_wildcard(content, full_path, external_key_parts)

    def __get_wildcards_in_text_file(self, full_path, base):
        """
        Get all wildcards in a text file.

        Args:
            full_path (str): The path to the file.
            base (str): The base path for the wildcards.
        """
        external_key: str = os.path.relpath(os.path.splitext(full_path)[0], base)
        external_key_parts = external_key.split(os.sep)
        with open(full_path, "r", encoding="utf-8") as file:
            text_content = map(lambda x: x.strip("\n\r"), file.readlines())
        text_content = list(filter(lambda x: x.strip() != "" and not x.strip().startswith("#"), text_content))
        text_content = [x.split("#")[0].rstrip() if len(x.split("#")) > 1 else x for x in text_content]
        self.__add_wildcard(text_content, full_path, external_key_parts)

    def __get_wildcards_in_directory(self, base: str, directory: str):
        """
        Get all wildcards in a directory.

        Args:
            base (str): The base path for the wildcards.
            directory (str): The path to the directory.
        """
        if not os.path.exists(directory):
            self.__logger.warning(f"Wildcard directory '{directory}' does not exist!")
            return
        for filename in os.listdir(directory):
            full_path = os.path.abspath(os.path.join(directory, filename))
            if os.path.basename(full_path).startswith("."):
                continue
            if os.path.isdir(full_path):
                self.__get_wildcards_in_directory(base, full_path)
            elif os.path.isfile(full_path):
                self.__get_wildcards_in_file(base, full_path)
