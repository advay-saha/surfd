"""Load, validate, edit and reset surfd.toml.

The effective configuration is the system defaults with the user's file
layered on top, so a user file only needs the keys it changes and new
settings added by upgrades always have a value.

Edits go through tomlkit so the user's comments and ordering survive.
"""

from __future__ import annotations

import copy
import datetime as _dt
import os
import shutil
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit

from . import keys, paths, schema


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Problem:
    level: str  # "error" | "warning"
    key: str
    message: str

    def __str__(self) -> str:
        return f"{self.level}: {self.key}: {self.message}"


# ------------------------------------------------------------------ loading --

def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from None
    except OSError as e:
        raise ConfigError(f"{path}: {e.strerror}") from None


def load_defaults() -> dict[str, Any]:
    path = paths.system_defaults()
    if not path.exists():
        raise ConfigError(f"system defaults missing: {path} (is surfd-default-config installed?)")
    return _read_toml(path)


def load_user() -> dict[str, Any]:
    path = paths.user_config()
    return _read_toml(path) if path.exists() else {}


def merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge tables; scalars and arrays in `over` replace `base`."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load() -> dict[str, Any]:
    return merge(load_defaults(), load_user())


def get(cfg: dict[str, Any], dotted: str, default: Any = None) -> Any:
    node: Any = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


# --------------------------------------------------------------- validation --

def validate(cfg: dict[str, Any], *, check_theme: bool = True) -> list[Problem]:
    problems: list[Problem] = []
    for dotted, fld in schema.SCHEMA.items():
        value = get(cfg, dotted)
        if value is None:
            problems.append(Problem("error", dotted, "missing (run `surfctl reset " + dotted.split(".")[0] + "`)"))
            continue
        msg = fld.check(value)
        if msg:
            problems.append(Problem("error", dotted, msg))

    # Unknown keys are warnings: probably a typo, but never fatal.
    known_sections = set(schema.sections())
    for section, table in cfg.items():
        if section not in known_sections:
            problems.append(Problem("warning", section, "unknown section (ignored)"))
            continue
        if not isinstance(table, dict):
            problems.append(Problem("error", section, "must be a table like [" + section + "]"))
            continue
        for key in table:
            dotted = f"{section}.{key}"
            if dotted not in schema.SCHEMA and dotted not in schema.FREEFORM_TABLES:
                problems.append(Problem("warning", dotted, "unknown setting (ignored)"))

    for msg in keys.binding_problems(cfg):
        problems.append(Problem("error", "keys.bindings", msg.split(": ", 1)[-1]))

    wp = get(cfg, "wallpaper.path", "")
    if isinstance(wp, str) and wp and not Path(os.path.expanduser(wp)).is_file():
        problems.append(Problem("warning", "wallpaper.path", f"file not found: {wp} (theme wallpaper will be used)"))

    if check_theme:
        from . import themes  # local import: themes imports config helpers

        name = get(cfg, "theme.name", "")
        if isinstance(name, str) and name and themes.find(name) is None:
            problems.append(Problem("error", "theme.name",
                                    f"theme '{name}' not found (installed: {', '.join(themes.names()) or 'none'})"))
    return problems


def errors(problems: list[Problem]) -> list[Problem]:
    return [p for p in problems if p.level == "error"]


# ------------------------------------------------------------------ editing --

def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o644)  # mkstemp creates 0600; configs are ordinary files
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def ensure_user_config() -> Path:
    """Create ~/.config/surfd/surfd.toml from the defaults if it is missing."""
    path = paths.user_config()
    if not path.exists():
        src = paths.system_defaults()
        if not src.exists():
            raise ConfigError(f"system defaults missing: {src}")
        _atomic_write(path, src.read_text(encoding="utf-8"))
    return path


def _load_doc() -> tomlkit.TOMLDocument:
    path = ensure_user_config()
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except Exception as e:  # tomlkit raises several parse error types
        raise ConfigError(f"{path}: {e}") from None


def set_values(changes: dict[str, Any], *, validate_result: bool = True) -> dict[str, Any]:
    """Set several dotted keys at once (validated together, written once).

    Values may be raw strings (as typed on the command line) or native
    Python values. Returns the coerced values.
    """
    coerced: dict[str, Any] = {}
    for dotted, raw in changes.items():
        if dotted.startswith("keys.bindings."):
            coerced[dotted] = str(raw)
            continue
        fld = schema.field_for(dotted)
        try:
            value = fld.coerce(raw)
        except (schema.SchemaError, ValueError) as e:
            raise ConfigError(f"{dotted}: {e}") from None
        msg = fld.check(value)
        if msg:
            raise ConfigError(f"{dotted}: {msg}")
        coerced[dotted] = value

    doc = _load_doc()
    for dotted, value in coerced.items():
        if dotted.startswith("keys.bindings."):
            section_path, leaf = ["keys", "bindings"], dotted[len("keys.bindings."):]
        else:
            *section_path, leaf = dotted.split(".")
        node: Any = doc
        for part in section_path:
            if part not in node:
                node[part] = tomlkit.table()
            node = node[part]
        node[leaf] = value

    if validate_result:
        candidate = merge(load_defaults(), doc.unwrap())
        errs = errors(validate(candidate))
        if errs:
            raise ConfigError("; ".join(str(e) for e in errs))

    _atomic_write(paths.user_config(), tomlkit.dumps(doc))
    return coerced


def set_value(dotted: str, raw: Any) -> Any:
    return set_values({dotted: raw})[dotted]


def unset_binding(combo: str) -> None:
    """Remove a binding, disabling it even if it is a default."""
    doc = _load_doc()
    if "keys" not in doc:
        doc["keys"] = tomlkit.table()
    if "bindings" not in doc["keys"]:
        doc["keys"]["bindings"] = tomlkit.table()
    doc["keys"]["bindings"][combo] = "none"
    _atomic_write(paths.user_config(), tomlkit.dumps(doc))


# ------------------------------------------------------------ reset/backups --

def backup() -> Path | None:
    """Copy the user's surfd.toml to the backups folder. Returns the copy."""
    src = paths.user_config()
    if not src.exists():
        return None
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    dest = paths.backups_dir() / f"surfd-{stamp}.toml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def list_backups() -> list[Path]:
    d = paths.backups_dir()
    return sorted(d.glob("surfd-*.toml"), reverse=True) if d.exists() else []


def reset(section: str | None = None) -> Path | None:
    """Reset everything, or one [section], to the defaults. Backs up first."""
    saved = backup()
    defaults_text = paths.system_defaults().read_text(encoding="utf-8")
    if section is None:
        _atomic_write(paths.user_config(), defaults_text)
        return saved
    if section not in schema.sections() and section != "keys":
        raise ConfigError(f"unknown section '{section}' (sections: {', '.join(schema.sections())})")
    defaults_doc = tomlkit.parse(defaults_text)
    doc = _load_doc()
    if section in defaults_doc:
        doc[section] = defaults_doc[section]
    elif section in doc:
        del doc[section]
    _atomic_write(paths.user_config(), tomlkit.dumps(doc))
    return saved


def restore(backup_path: Path) -> Path | None:
    if not backup_path.is_file():
        raise ConfigError(f"no such backup: {backup_path}")
    _read_toml(backup_path)  # refuse to restore a broken file
    saved = backup()
    _atomic_write(paths.user_config(), backup_path.read_text(encoding="utf-8"))
    return saved
