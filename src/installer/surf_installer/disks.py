"""Which disks can surfd be installed on?"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Disk:
    path: str
    size: int
    model: str
    transport: str
    removable: bool

    @property
    def size_label(self) -> str:
        return human_size(self.size)

    @property
    def title(self) -> str:
        return self.model or os.path.basename(self.path)

    @property
    def subtitle(self) -> str:
        kind = {"nvme": "NVMe SSD", "sata": "SATA", "usb": "USB", "mmc": "SD/eMMC", "virtio": "virtual disk",
                "scsi": "SCSI"}.get(self.transport, self.transport or "disk")
        return f"{self.size_label} · {kind} · {self.path}"


def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for unit in units:
        if size < 1000 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit in ("B", "KB") or size >= 100 else f"{size:.1f} {unit}"
        size /= 1000
    return f"{n} B"


def live_medium_disks() -> set[str]:
    """Disks backing the running live system (never offer to erase them)."""
    found: set[str] = set()
    for mnt in ("/run/initramfs/live", "/run/initramfs/isoscan"):
        r = subprocess.run(["findmnt", "-n", "-o", "SOURCE", mnt], capture_output=True, text=True, check=False)
        src = r.stdout.strip()
        if not src.startswith("/dev/"):
            continue
        parent = subprocess.run(["lsblk", "-n", "-o", "PKNAME", src], capture_output=True, text=True, check=False)
        name = parent.stdout.strip().splitlines()[0] if parent.stdout.strip() else ""
        found.add(f"/dev/{name}" if name else src)
    return found


def parse_lsblk(text: str, exclude: set[str]) -> list[Disk]:
    data = json.loads(text)
    disks = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        path = dev.get("path") or f"/dev/{dev.get('name')}"
        name = os.path.basename(path)
        if name.startswith(("zram", "loop", "sr", "fd", "ram")) or path in exclude:
            continue
        if str(dev.get("ro")) in ("1", "True", "true"):
            continue
        tran = (dev.get("tran") or "").lower()
        if not tran and name.startswith("vd"):
            tran = "virtio"
        if not tran and name.startswith("mmcblk"):
            tran = "mmc"
        disks.append(Disk(path=path, size=int(dev.get("size") or 0), model=(dev.get("model") or "").strip(),
                          transport=tran, removable=str(dev.get("rm")) in ("1", "True", "true")))
    disks.sort(key=lambda d: (d.removable, d.path))
    return disks


def list_disks() -> list[Disk]:
    fake = os.environ.get("SURF_INSTALLER_FAKE_DISKS")
    if fake:
        return parse_lsblk(Path(fake).read_text(), set())
    r = subprocess.run(["lsblk", "-J", "-b", "-d", "-o", "NAME,PATH,SIZE,TYPE,MODEL,TRAN,RM,RO"],
                       capture_output=True, text=True, check=True)
    return parse_lsblk(r.stdout, live_medium_disks())
