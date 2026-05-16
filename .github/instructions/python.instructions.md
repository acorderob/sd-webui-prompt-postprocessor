---
description: "Use when writing, editing, or reviewing Python code."
applyTo: "**/*.py"
---
# Python code

## Python 3.10 Compatibility

All Python code must be compatible with Python 3.10. Do not use language features or standard-library additions introduced in 3.11 or later.

### Forbidden (3.11+)

| Avoid | Use instead |
|-------|-------------|
| `tomllib` (stdlib) | `tomli` (third-party) or conditional `try/except ImportError` |
| `typing.Self` | `TypeVar("Self", bound="ClassName")` or `from __future__ import annotations` |
| `typing.Never` | `typing.NoReturn` |
| `typing.TypeVarTuple`, `typing.Unpack` | `typing_extensions` backports |
| `StrEnum` | `class MyEnum(str, enum.Enum)` |
| `except*` / `ExceptionGroup` | Not available; raise/catch normally |
| `asyncio.TaskGroup`, `asyncio.timeout()` | `asyncio.gather()` / `asyncio.wait_for()` |

### Forbidden (3.12+)

| Avoid | Use instead |
|-------|-------------|
| `type X = ...` (type alias statement) | `X: TypeAlias = ...` with `typing.TypeAlias` |
| `def f[T](...)` / `class C[T]` generic syntax | `TypeVar` + `Generic[T]` |
| `@typing.override` | Omit or use comment |
| `itertools.batched()` | Manual chunking or `more-itertools` |

### Safe to use (available in 3.10)

- `match`/`case` structural pattern matching
- `X | Y` union type syntax in annotations (e.g., `int | None`)
- `typing.TypeAlias`, `typing.ParamSpec`
- `list[int]`, `dict[str, int]` — built-in generic aliases
- `zip(..., strict=True)`
- `str.removeprefix()` / `str.removesuffix()`

## Paths

Use `pathlib.Path` for filesystem paths instead of `str` paths or `os.path`.

## Comments

Do not use emdashes (—) in comments. Use a single dash (-) or parentheses instead. Also avoid any other typographical punctuation that is not basic ASCII.
