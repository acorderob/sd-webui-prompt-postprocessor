from collections import OrderedDict
from typing import Tuple


class PPPLRUCache:

    ProcessInput = Tuple[int, int, str, str]  # (seed, wildcards_hash, positive_prompt, negative_prompt)
    ProcessResult = Tuple[str, str]  # (positive_prompt, negative_prompt)

    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

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
