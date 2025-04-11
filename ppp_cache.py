from collections import OrderedDict
from logging import Logger
from typing import Tuple

from ppp_logging import DEBUG_LEVEL  # pylint: disable=import-error


class PPPLRUCache:

    ProcessInput = Tuple[int, int, str, str]  # (seed, wildcards_hash, positive_prompt, negative_prompt)
    ProcessResult = Tuple[str, str]  # (positive_prompt, negative_prompt)

    def __init__(self, capacity: int, logger: Logger = None, debug_level: DEBUG_LEVEL = DEBUG_LEVEL.none):
        self.cache = OrderedDict()
        self.capacity = capacity
        self._logger = logger
        self._debug_level = debug_level

    def get(self, key: ProcessInput) -> ProcessResult:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: ProcessInput, value: ProcessResult) -> None:
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
        # if self._logger is not None and self._debug_level != DEBUG_LEVEL.none:
        #     self._logger.debug(f"Cache size: {self.cache.__sizeof__()}")
