"""What the user chose in the wizard, and the checks it must pass.

The plan travels from the (unprivileged) wizard to the (root) engine as a
JSON file readable only by its owner; the engine deletes it after reading
because it contains the account password and disk passphrase.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

MIN_DISK_BYTES = 20 * 1024**3
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
HOSTNAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
LOCALE_RE = re.compile(r"^[a-z]{2,3}(_[A-Z]{2})?(\.UTF-8)?(@[a-z]+)?$")
RESERVED_USERS = {"root", "bin", "daemon", "adm", "lp", "sync", "shutdown", "halt", "mail", "operator", "games",
                  "ftp", "nobody", "liveuser", "surfd-greeter", "systemd-network", "dbus", "polkitd", "sshd",
                  "tss", "chrony", "pipewire", "geoclue", "rtkit", "colord", "avahi"}


class PlanError(ValueError):
    pass


@dataclass
class Plan:
    disk: str = ""  # /dev/nvme0n1
    disk_size: int = 0  # bytes, for the size check
    encrypt: bool = False
    passphrase: str = ""
    fullname: str = ""
    username: str = ""
    password: str = ""
    hostname: str = "surfd"
    timezone: str = "UTC"
    locale: str = "en_US.UTF-8"
    keyboard_layout: str = "us"
    keyboard_variant: str = ""
    firmware: str = "auto"  # auto | uefi | bios
    root_fs: str = "btrfs"  # btrfs (default: compression, "root"/"home" subvolumes) | ext4
    source: str = ""  # live root filesystem; auto-detected when empty
    extras: dict[str, str] = field(default_factory=dict)

    # ---------------------------------------------------------------- checks --
    def problems(self, *, zoneinfo: Path = Path("/usr/share/zoneinfo")) -> dict[str, str]:
        """Field -> human message for everything that is wrong (empty = valid)."""
        p: dict[str, str] = {}
        if not self.disk.startswith("/dev/"):
            p["disk"] = "Choose the disk to install on."
        elif self.disk_size and self.disk_size < MIN_DISK_BYTES:
            p["disk"] = f"This disk is too small; surfd needs at least {MIN_DISK_BYTES // 1024**3} GB."
        if self.encrypt and len(self.passphrase) < 8:
            p["passphrase"] = "Use at least 8 characters for the encryption passphrase."
        if not self.fullname.strip():
            p["fullname"] = "Enter your name."
        if not USERNAME_RE.match(self.username):
            p["username"] = "Use lowercase letters, digits, '-' or '_', starting with a letter (max 32)."
        elif self.username in RESERVED_USERS:
            p["username"] = f"'{self.username}' is reserved by the system; choose another."
        if not self.password:
            p["password"] = "Choose a password."
        elif ":" in self.password or "\n" in self.password:
            p["password"] = "The password cannot contain ':' or line breaks."
        if not HOSTNAME_RE.match(self.hostname):
            p["hostname"] = "Use letters, digits and '-' (no spaces), up to 63 characters."
        if not self.timezone or ".." in self.timezone or (zoneinfo.is_dir() and not (zoneinfo / self.timezone).is_file()):
            p["timezone"] = "Choose a time zone."
        if not LOCALE_RE.match(self.locale):
            p["locale"] = "Choose a language."
        if not re.match(r"^[a-z]{2,8}(,[a-z]{2,8})*$", self.keyboard_layout):
            p["keyboard_layout"] = "Choose a keyboard layout."
        if self.firmware not in ("auto", "uefi", "bios"):
            p["firmware"] = "Unknown firmware type."
        if self.root_fs not in ("btrfs", "ext4"):
            p["root_fs"] = "The root file system must be btrfs or ext4."
        return p

    def check(self) -> None:
        problems = self.problems()
        if problems:
            raise PlanError("; ".join(f"{k}: {v}" for k, v in problems.items()))

    # ---------------------------------------------------------- transport --
    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh)

    @classmethod
    def read(cls, path: Path, *, consume: bool = False) -> Plan:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise PlanError(f"cannot read install plan {path}: {e}") from None
        finally:
            if consume:
                try:
                    path.unlink()
                except OSError:
                    pass
        known = set(cls.__dataclass_fields__)
        unknown = set(data) - known
        if unknown:
            raise PlanError(f"unknown plan fields: {', '.join(sorted(unknown))}")
        return cls(**data)

    def redacted(self) -> dict[str, object]:
        d = asdict(self)
        for secret in ("password", "passphrase"):
            if d.get(secret):
                d[secret] = "********"
        return d


def suggest_username(fullname: str) -> str:
    """'Advay Saha' -> 'advay'."""
    first = (fullname.strip().split() or [""])[0].lower()
    cleaned = re.sub(r"[^a-z0-9_-]", "", first)
    if cleaned and not cleaned[0].isalpha():
        cleaned = "u" + cleaned
    return cleaned[:32]
