import logging
from pathlib import Path
from typing import Any


def get_version_from_pyproject() -> str:
    """
    Reads the version from the pyproject.toml file.

    Returns:
        str: The version string.
    """
    version_str = "0.0.0"
    try:
        pyproject_path = Path(__file__).resolve().parent / "pyproject.toml"
        with open(pyproject_path, "r", encoding="utf-8") as file:
            for line in file:
                if line.startswith("version = "):
                    version_str = line.split("=")[1].strip().strip('"')
                    break
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.getLogger().exception(e)
    return version_str


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


def escape_single_quotes(s: str):
    """
    Escape single quotes in a string.

    Args:
        s (str): The string to escape.

    Returns:
        str: The escaped string.
    """
    return s.replace("'", "\\'")


def escape_double_quotes(s: str):
    """
    Escape double quotes in a string.

    Args:
        s (str): The string to escape.

    Returns:
        str: The escaped string.
    """
    return s.replace('"', '\\"')


def repr_value(s: Any):
    """
    Return a string representation of a value, escaping single quotes.

    Args:
        s (Any): The value to represent.
    Returns:
        str: The string representation of the value.
    """
    if isinstance(s, str):
        return f"'{escape_single_quotes(s)}'"
    if isinstance(s, bool):
        return "true" if s else "false"
    return str(s)


def format_output(text: str) -> str:
    """
    Formats the output text by encoding it using unicode_escape and decoding it using utf-8.

    Args:
        text (str): The input text to be formatted.

    Returns:
        str: The formatted output text.
    """
    return text.encode("unicode_escape").decode("utf-8")
