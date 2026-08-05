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

Use the `process()` helper from the base class — never instantiate `PromptPostProcessor` directly in test methods unless there is a need to pass specific options not covered by the default setup or the "nocup" or "nostrict" options.

```python
def test_cl_simple(self):
    """simple cleanup"""
    self.process(
        InputTuple(
            "input prompt",                         # positive prompt
            ""),                                    # negative prompt
        OutputTuple(
            "expected output",                      # expected positive prompt
            "",                                     # expected negative prompt
            {}                                      # expected variables (optional)
        ),
    )

def test_cl_combinatorial(self):
    """simple cleanup"""
    self.process(
        InputTuple(
            "input prompt",                         # positive prompt
            ""),                                    # negative prompt
        [
            OutputTuple(
                "expected output",                  # expected positive prompt
                "",                                 # expected negative prompt
                {}                                  # expected variables (optional)
            ),
            OutputTuple(
                "expected output",                  # expected positive prompt
                "",                                 # expected negative prompt
                {}                                  # expected variables (optional)
            ),
        ],
        ppp=self.init_ppp(None, run_mode=RUN_MODE.combinatorial),
    )

```

### `process()` Signature (key parameters)

| Parameter | Type | Notes |
|-----------|------|-------|
| `input_prompts` | `InputTuple` | Prompts input |
| `expected_output` | `OutputTuple \| list[OutputTuple]` | Single or multiple valid outputs |
| `seed` | `int` | Optional, defaults to fixed seed |
| `ppp` | `PromptPostProcessor \| str \| None` | Supported values `"nocup"`, `"nostrict"` or a specific instance |
| `interrupted` | `bool` | Expected interrupt flag |
| `specific_wc_folders` | `list[Path]` | Optional list of specific wildcard folders to use for this test |
| `specific_em_folders` | `list[Path]` | Optional list of specific extranetwork folders to use for this test |
| `input_vars` | `dict[str, Any]` | Optional dictionary of input variables to set before processing |


## Assertions

Use `assertEqual` or similar methods with a descriptive message string:

```python
self.assertEqual(result, expected, "Descriptive failure message")
self.assertIn(key, container, f"Key '{key}' not found in output")
```

Do not use bare `assert` statements.

## Default Options & Environment

Override `self.defopts` or `self.def_env_info` to pass non-default options.

```python

def test_cl_custom1(self):  # only option changes
    """cleanup with custom separator"""
    self.process(
        InputTuple("a, , b", ""),
        OutputTuple("a | b", ""),
        ppp=self.init_ppp(
            None,
            keep_choices_order=True,
            cup_do_cleanup=False,
            run_mode=RUN_MODE.combinatorial,
        ),
    )

def test_cl_custom2(self):  # only environment changes
    """cleanup with custom separator"""
    self.process(
        InputTuple("a, , b", ""),
        OutputTuple("a | b", ""),
        ppp=PromptPostProcessor(
            self.ppp_logger,
            replace(
                self.def_env_info,
                model_filename="./webui/models/Stable-diffusion/testmodel.safetensors",
            ),
            self.defopts,
            self.grammar_content,
            self.interrupt,
            self.wildcards_obj,
            self.extranetwork_maps_obj,
        ),
    )
```

## Entry Point

Every test file must start with:

```python
if __name__ == "__main__":
    raise SystemExit("This script must not be run directly")
```
