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


def format_output(text: str) -> str:
    """
    Formats the output text by encoding it using unicode_escape and decoding it using utf-8.

    Args:
        text (str): The input text to be formatted.

    Returns:
        str: The formatted output text.
    """
    return text.encode("unicode_escape").decode("utf-8")
