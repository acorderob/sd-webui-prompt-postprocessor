from typing import Any


class VariableRepository:
    """
    Unified repository for system, user, and echoed prompt variables.

    System variables (underscore-prefixed names like ``_model``) are populated
    once per processing session and are read-only during prompt evaluation.

    User variables are created and mutated by set/echo constructs in the prompt.

    Echoed variables record which user variables have already been output and
    with what resolved string value.
    """

    def __init__(self) -> None:
        self._system: dict[str, Any] = {}
        self._user: dict[str, Any] = {}
        self._echoed: dict[str, str] = {}

    def name_is_system(self, name: str) -> bool:
        """Return True if *name* is a system variable (i.e. starts with an underscore)."""
        return name.startswith("_")

    # ---- System variables ----

    def get_system(self, name: str, default: Any = None) -> Any:
        """Return the value of a system variable, or *default* if absent."""
        return self._system.get(name, default)

    def set_system(self, name: str, value: Any) -> None:
        """Set a system variable."""
        if not self.name_is_system(name):
            raise ValueError(f"invalid system variable name '{name}': must start with an underscore")
        self._system[name] = value

    def update_system(self, mapping: dict[str, Any]) -> None:
        """Bulk-update system variables from *mapping*."""
        for name in mapping:
            if not self.name_is_system(name):
                raise ValueError(f"invalid system variable name '{name}': must start with an underscore")
        self._system.update(mapping)

    def clear_system(self) -> None:
        """Remove all system variables."""
        self._system.clear()

    def get_all_system(self) -> dict[str, Any]:
        """Return a shallow copy of all system variables."""
        return {x: self._system[x] for x in sorted(self._system.keys())}

    # ---- User variables ----

    def get_user(self, name: str, default: Any = None) -> Any:
        """Return the value of a user variable, or *default* if absent."""
        return self._user.get(name, default)

    def set_user(self, name: str, value: Any) -> None:
        """Set a user variable."""
        if self.name_is_system(name):
            raise ValueError(f"invalid user variable name '{name}': must not start with an underscore")
        self._user[name] = value

    def delete_user(self, name: str) -> None:
        """Remove a user variable (no-op if it does not exist)."""
        self._user.pop(name, None)

    def clear_user(self) -> None:
        """Remove all user variables."""
        self._user.clear()

    # ---- Echoed variables ----

    def get_echoed_value(self, name: str, default: str | None = None) -> str | None:
        """Return the echoed string value for *name*, or *default* if not echoed."""
        return self._echoed.get(name, default)

    def echo(self, name: str, value: str) -> None:
        """Record that *name* was echoed with *value*."""
        self._echoed[name] = value

    def clear_echoed(self) -> None:
        """Remove all echoed-variable records."""
        self._echoed.clear()

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
        return self._user.get(name, default)

    def all_user_or_echoed_keys(self) -> set[str]:
        """Return the union of user-variable and echoed-variable keys."""
        return set(self._user.keys()) | set(self._echoed.keys())

    # ---- State backup / restore ----

    def backup_user_and_echoed(self) -> tuple[dict[str, Any], dict[str, str]]:
        """Return shallow-copy snapshots of user and echoed variables for rollback."""
        return self._user.copy(), self._echoed.copy()

    def restore_user_and_echoed(self, backup: tuple[dict[str, Any], dict[str, str]]) -> None:
        """Restore user and echoed variables from a snapshot made by :meth:`backup_user_and_echoed`."""
        user_backup, echoed_backup = backup
        self._user.clear()
        self._user.update(user_backup)
        self._echoed.clear()
        self._echoed.update(echoed_backup)
