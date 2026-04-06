---
description: "Use when writing, editing, or reviewing test files. Enforces unittest patterns used in this project: TestCase inheritance, base class setup, process() helper, and naming conventions."
applyTo: "tests/**/*.py"
---
# Test Conventions

All tests use the standard `unittest` module. Do **not** use pytest-specific features (fixtures, `@pytest.mark`, `conftest.py`, etc.).

## File & Class Naming

- One test file per concern, named `tests_{category}.py`
- One test class per file inheriting from `TestPromptPostProcessorBase`:

```python
import unittest
from tests.base_tests import TestPromptPostProcessorBase

class TestMyFeature(TestPromptPostProcessorBase):

    def setUp(self):
        super().setUp(enable_file_logging=False)
```

## Test Method Naming

```
test_{2-3 letter category prefix}_{short_description}
```

Examples: `test_cl_simple`, `test_ch_choices`, `test_wc_ignore`

## Running a Test Case via `self.process()`

Use the `process()` helper from the base class — never instantiate `PromptPostProcessor` directly in test methods.

```python
def test_cl_simple(self):
    """simple cleanup"""
    self.process(
        "input prompt",                             # positive prompt
        "",                                         # negative prompt
        PromptPair("expected output", ""),          # expected result
    )
```

### `process()` Signature (key parameters)

| Parameter | Type | Notes |
|-----------|------|-------|
| `input_prompt` | `str` | Positive prompt input |
| `input_negative_prompt` | `str` | Negative prompt input |
| `expected_output` | `PromptPair \| list[PromptPair]` | Single or multiple valid outputs |
| `seed` | `int` | Optional, defaults to fixed seed |
| `ppp` | `PromptPostProcessor \| str \| None` | Pass `"nocup"` to skip creation |
| `interrupted` | `bool` | Expected interrupt flag |
| `output_variables` | `dict[str, str] \| None` | Variables to validate after processing |

## Assertions

Use `assertEqual` with a descriptive message string:

```python
self.assertEqual(result, expected, "Descriptive failure message")
self.assertIn(key, container, f"Key '{key}' not found in output")
```

Do not use bare `assert` statements.

## Default Options & Environment

Override `self.defopts` or `self.def_env_info` to pass non-default options — do not hardcode option dicts from scratch:

```python
def test_cl_custom(self):
    """cleanup with custom separator"""
    opts = {**self.defopts, "ppp_stn_separator": " | "}
    self.process("a, , b", "", PromptPair("a | b", ""), ppp_opts=opts)
```

## Entry Point

Every test file must start with:

```python
if __name__ == "__main__":
    raise SystemExit("This script must not be run directly")
```
