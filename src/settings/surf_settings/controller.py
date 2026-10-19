"""The single path from a widget to the desktop: validate, write, apply.

Surf Settings never writes config files itself. It calls the same surfd
library surfctl uses, so the GUI, the CLI and hand edits always agree.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from gi.repository import GLib

from surfd import config, generate, keys, session, themes

ERRORS = (config.ConfigError, themes.ThemeError, keys.BindingError, RuntimeError, ValueError)


class Controller:
    """Batches rapid changes (sliders, typing) and applies them once."""

    def __init__(self, on_error: Callable[[str], None], on_applied: Callable[[str], None]) -> None:
        self.on_error = on_error
        self.on_applied = on_applied
        self.pending: dict[str, Any] = {}
        self._timer = 0
        self.cfg: dict[str, Any] = {}
        self.listeners: list[Callable[[dict[str, Any]], None]] = []
        self.reload_config()

    # ------------------------------------------------------------------ read --
    def reload_config(self) -> None:
        try:
            config.ensure_user_config()
            self.cfg = config.load()
        except config.ConfigError as e:
            self.cfg = config.load_defaults()
            self.on_error(f"Your surfd.toml has an error, showing defaults: {e}")

    def get(self, dotted: str) -> Any:
        return config.get(self.cfg, dotted)

    # ----------------------------------------------------------------- write --
    def change(self, dotted: str, value: Any, *, delay_ms: int = 350) -> None:
        self.pending[dotted] = value
        if self._timer:
            GLib.source_remove(self._timer)
        self._timer = GLib.timeout_add(delay_ms, self._flush)

    def change_now(self, changes: dict[str, Any]) -> bool:
        self.pending.update(changes)
        return self._flush() is GLib.SOURCE_REMOVE and not self.pending

    def _flush(self) -> bool:
        self._timer = 0
        if not self.pending:
            return GLib.SOURCE_REMOVE
        changes, self.pending = self.pending, {}
        user_file = config.paths.user_config()
        previous = user_file.read_text(encoding="utf-8") if user_file.exists() else None
        try:
            config.set_values(changes)
            ctx = generate.build_context()
            session.regenerate_and_reload(ctx)
        except ERRORS as e:
            if previous is not None:
                config._atomic_write(user_file, previous)
            self.on_error(str(e))
            self.reload_config()
            self._notify()
            return GLib.SOURCE_REMOVE
        self.reload_config()
        self._notify()
        self.on_applied("Applied" if session.in_sway() else "Saved — applies at next login")
        return GLib.SOURCE_REMOVE

    def reset(self, section: str | None = None) -> str | None:
        try:
            saved = config.reset(section)
            session.regenerate_and_reload(generate.build_context())
        except ERRORS as e:
            self.on_error(str(e))
            return None
        self.reload_config()
        self._notify()
        return str(saved) if saved else ""

    def restore_latest(self) -> bool:
        backups = config.list_backups()
        if not backups:
            self.on_error("There are no backups yet.")
            return False
        try:
            config.restore(backups[0])
            session.regenerate_and_reload(generate.build_context())
        except ERRORS as e:
            self.on_error(str(e))
            return False
        self.reload_config()
        self._notify()
        return True

    # ------------------------------------------------------------- listeners --
    def subscribe(self, fn: Callable[[dict[str, Any]], None]) -> None:
        self.listeners.append(fn)

    def _notify(self) -> None:
        for fn in self.listeners:
            fn(self.cfg)
