from dataclasses import dataclass, field
from typing import Any

ScalarValue = str | int | float | bool
VariableValue = ScalarValue | list | None


@dataclass
class VariableEntry:
    """Holds all state for a single user variable."""

    value: Any = field(default=None)  # raw unevaluated value or evaluated on set
    last_echoed_value: Any = field(default=None)  # raw unevaluated value at last echo
    last_echoed_evaluated_value: ScalarValue | None = field(default=None)  # evaluated value at last echo


class VariableRepository:
    """
    Unified repository for system and user prompt variables.

    System variables (underscore-prefixed names like ``_model``) are populated
    once per processing session and are read-only during prompt evaluation.

    User variables are created and mutated by set/echo constructs in the prompt.
    Each user variable is stored as a :class:`VariableEntry` that tracks the
    set value and the last value that was echoed into the prompt output.
    """

    def __init__(self) -> None:
        self._system: dict[str, VariableValue] = {}
        self._vars: dict[str, VariableEntry] = {}

    def name_is_system(self, name: str) -> bool:
        """Return True if *name* is a system variable (i.e. starts with an underscore)."""
        return name.startswith("_")

    # ---- System variables ----

    def get_system(self, name: str, default: VariableValue = None) -> VariableValue:
        """Return the value of a system variable, or *default* if absent."""
        return self._system.get(name, default)

    def set_system(self, name: str, value: VariableValue) -> None:
        """Set a system variable."""
        if not self.name_is_system(name):
            raise ValueError(f"Invalid system variable name '{name}': must start with an underscore")
        if value is None:
            self._system.pop(name, None)
        else:
            self._system[name] = value

    def update_system(self, mapping: dict[str, VariableValue]) -> None:
        """Bulk-update system variables from *mapping*."""
        for name in mapping:
            if not self.name_is_system(name):
                raise ValueError(f"Invalid system variable name '{name}': must start with an underscore")
        self._system.update(mapping)

    def clear_system(self) -> None:
        """Remove all system variables."""
        self._system.clear()

    @property
    def all_system(self) -> dict[str, VariableValue]:
        """Return a shallow copy of all system variables."""
        return self._system.copy()

    # ---- User variables ----

    def _entry(self, name: str) -> VariableEntry:
        """Return (creating if necessary) the :class:`VariableEntry` for *name*."""
        if name not in self._vars:
            self._vars[name] = VariableEntry()
        return self._vars[name]

    def get_user(self, name: str, default: Any = None) -> Any:
        """Return the value of a user variable, or *default* if absent."""
        entry = self._vars.get(name)
        if entry is None or entry.value is None:
            return default
        return entry.value

    def set_user(self, name: str, value: Any) -> None:
        """Set the value of a user variable."""
        if self.name_is_system(name):
            raise ValueError(f"Invalid user variable name '{name}': must not start with an underscore")
        entry = self._entry(name)
        entry.value = value

    def delete_user(self, name: str) -> None:
        """
        Remove the value for a user variable.
        """
        entry = self._vars.get(name)
        if entry is None:
            return
        del self._vars[name]

    def clear_user(self) -> None:
        """
        Clear the values for all user variables.
        """
        self._vars.clear()

    @property
    def all_user(self) -> set[str]:
        """Return the set of all user-variable keys (those with any non-None field)."""
        return set(self._vars)

    def set_echoed_value(self, name: str, value: Any, evaluated_value: ScalarValue) -> None:
        """Record that *name* was echoed into the prompt with *value*."""
        if not self.name_is_system(name):
            entry = self._entry(name)
            entry.last_echoed_value = value
            entry.last_echoed_evaluated_value = evaluated_value

    def get_echoed_value(self, name: str, default: ScalarValue | None = None) -> ScalarValue | None:
        """Return the last echoed value for *name*, or *default* if it has not been echoed."""
        entry = self._vars.get(name)
        if entry is None:
            return default
        return entry.last_echoed_evaluated_value if entry.last_echoed_evaluated_value is not None else default

    def backup_user(self) -> dict[str, VariableEntry]:
        """Return a per-entry shallow-copy snapshot of all user variables for rollback."""
        return {
            name: VariableEntry(entry.value, entry.last_echoed_value, entry.last_echoed_evaluated_value)
            for name, entry in self._vars.items()
        }

    def restore_user(self, backup: dict[str, VariableEntry]) -> None:
        """Restore user variables from a snapshot made by :meth:`backup_user_and_echoed`."""
        self._vars.clear()
        self._vars.update(
            {
                name: VariableEntry(entry.value, entry.last_echoed_value, entry.last_echoed_evaluated_value)
                for name, entry in backup.items()
            }
        )

    # ---- Combined queries ----

    def get(self, name: str, default: Any = None) -> Any:
        """
        Return the value of a variable, checking system variables first, then user variables.

        Args:
            name (str): The name of the variable.
            default (Any): The value to return if the variable is not found.
        """
        if name in self._system:
            return self._system.get(name, default)
        return self.get_user(name, default)
