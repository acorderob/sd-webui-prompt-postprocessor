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
