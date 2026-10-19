"""Real disk operations on a loop device: partition, LUKS2, mkfs, btrfs subvolumes,
mounting, rsync copy and fstab. Needs root, loop devices and the disk tools;
skipped otherwise. (Steps that need a real Fedora system — chroot, kernel-install,
GRUB, SELinux — are covered by the dry-run tests and the VM checklist.)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from surf_installer import engine
from surf_installer.plan import Plan

TOOLS = ["losetup", "sgdisk", "partprobe", "wipefs", "mkfs.vfat", "mkfs.ext4", "mkfs.btrfs", "btrfs",
         "cryptsetup", "rsync", "blkid"]
pytestmark = pytest.mark.skipif(os.geteuid() != 0 or any(shutil.which(t) is None for t in TOOLS)
                                or not Path("/dev/loop-control").exists(),
                                reason="needs root, loop devices and disk tools")

STEPS = {"partition", "encrypt", "format", "mount", "copy", "fstab", "finish"}


def _device_mapper_works() -> bool:
    if shutil.which("dmsetup") is None:
        return Path("/proc/misc").exists() and "device-mapper" in Path("/proc/misc").read_text()
    return subprocess.run(["dmsetup", "version"], capture_output=True, check=False).returncode == 0


DM = _device_mapper_works()
FILESYSTEMS = Path("/proc/filesystems").read_text() if Path("/proc/filesystems").exists() else ""
HAS_BTRFS = "btrfs" in FILESYSTEMS
HAS_VFAT = "vfat" in FILESYSTEMS


def sh(*cmd: str, input_text: str | None = None) -> str:
    return subprocess.run(cmd, input=input_text, capture_output=True, text=True, check=True).stdout


@pytest.fixture()
def loopdisk(tmp_path: Path):  # type: ignore[no-untyped-def]
    img = tmp_path / "disk.img"
    with img.open("wb") as fh:
        fh.truncate(24 * 1024**3)  # sparse 24 GB
    dev = sh("losetup", "-fP", "--show", str(img)).strip()
    yield dev
    subprocess.run(["umount", "-R", str(tmp_path / "target")], capture_output=True, check=False)
    for name in sh("dmsetup", "ls").split() if shutil.which("dmsetup") else []:
        if name.startswith("luks-"):
            subprocess.run(["cryptsetup", "close", name], capture_output=True, check=False)
    subprocess.run(["losetup", "-d", dev], check=False)


def fake_root(root: Path) -> None:
    (root / "etc").mkdir(parents=True)
    (root / "etc" / "os-release").write_text("ID=surfd\n")
    (root / "usr" / "bin").mkdir(parents=True)
    (root / "usr" / "bin" / "hello").write_text("#!/bin/sh\necho hi\n")
    os.chmod(root / "usr" / "bin" / "hello", 0o755)
    os.link(root / "usr" / "bin" / "hello", root / "usr" / "bin" / "hello-hardlink")
    (root / "bin").symlink_to("usr/bin")
    (root / "boot" / "efi" / "EFI" / "BOOT").mkdir(parents=True)
    (root / "boot" / "efi" / "EFI" / "BOOT" / "BOOTX64.EFI").write_bytes(b"MZ fake shim")
    (root / "home" / "liveuser").mkdir(parents=True)
    (root / "home" / "liveuser" / "junk").write_text("must not be copied")
    (root / "proc").mkdir()
    (root / "proc" / "junk").write_text("must not be copied")


def _needs(dm: bool = False, btrfs: bool = False, vfat: bool = False) -> list[pytest.MarkDecorator]:
    missing = [n for n, need, have in (("device-mapper", dm, DM), ("btrfs", btrfs, HAS_BTRFS),
                                       ("vfat", vfat, HAS_VFAT)) if need and not have]
    return [pytest.mark.skipif(bool(missing), reason=f"kernel lacks {', '.join(missing)}")]


@pytest.mark.parametrize("firmware,encrypt,root_fs", [
    pytest.param("bios", False, "ext4", marks=_needs()),
    pytest.param("bios", False, "btrfs", marks=_needs(btrfs=True)),
    pytest.param("uefi", False, "btrfs", marks=_needs(btrfs=True, vfat=True)),
    pytest.param("uefi", True, "btrfs", marks=_needs(dm=True, btrfs=True, vfat=True)),
])
def test_real_disk_install(tmp_path: Path, loopdisk: str, firmware: str, encrypt: bool, root_fs: str) -> None:
    src = tmp_path / "src"
    fake_root(src)
    plan = Plan(disk=loopdisk, firmware=firmware, encrypt=encrypt, passphrase="loop test passphrase",
                fullname="Test", username="test", password="pw", source=str(src), root_fs=root_fs)
    events: list[dict[str, object]] = []
    runner = engine.Runner(tmp_path / "install.log")
    eng = engine.Engine(plan, runner, target=tmp_path / "target", emit=events.append, live_root=tmp_path)
    eng.install(only=STEPS)

    # partition table
    table = sh("sgdisk", "-p", loopdisk)
    assert ("EF00" in table) == (firmware == "uefi") and ("EF02" in table) == (firmware == "bios")
    root_part = engine.part_path(loopdisk, 3)
    assert sh("blkid", "-s", "TYPE", "-o", "value", root_part).strip() == ("crypto_LUKS" if encrypt else root_fs)

    # reopen exactly as the installed system would: crypttab + fstab by UUID
    mnt = tmp_path / "check"
    mnt.mkdir()
    root_dev = root_part
    if encrypt:
        luks_uuid = sh("cryptsetup", "luksUUID", root_part).strip()
        crypttab = (eng.lay.uuids, luks_uuid)
        assert crypttab[0]["luks"] == luks_uuid
        sh("cryptsetup", "open", "--key-file=-", root_part, "luks-check", input_text=plan.passphrase)
        root_dev = "/dev/mapper/luks-check"
    try:
        sh("mount", *(["-o", "subvol=root"] if root_fs == "btrfs" else []), root_dev, str(mnt))
        fstab = (mnt / "etc" / "fstab").read_text()
        root_uuid = sh("blkid", "-s", "UUID", "-o", "value", root_dev).strip()
        boot_uuid = sh("blkid", "-s", "UUID", "-o", "value", engine.part_path(loopdisk, 2)).strip()
        assert f"UUID={root_uuid}  /          {root_fs}" in fstab
        assert f"UUID={boot_uuid}  /boot      ext4" in fstab
        if firmware == "uefi":
            esp_uuid = sh("blkid", "-s", "UUID", "-o", "value", engine.part_path(loopdisk, 1)).strip()
            assert f"UUID={esp_uuid}  /boot/efi  vfat" in fstab
        if encrypt:
            assert (mnt / "etc" / "crypttab").read_text().startswith(f"luks-{luks_uuid} UUID={luks_uuid}")
            assert f"rd.luks.uuid=luks-{luks_uuid}" in (mnt / "etc" / "kernel" / "cmdline").read_text()
        # copied content: links preserved, live-only and virtual paths excluded
        assert (mnt / "usr" / "bin" / "hello").stat().st_ino == (mnt / "usr" / "bin" / "hello-hardlink").stat().st_ino
        assert os.readlink(mnt / "bin") == "usr/bin"
        assert not (mnt / "proc" / "junk").exists()
        if root_fs == "btrfs":
            subvols = sh("btrfs", "subvolume", "list", str(mnt))
            assert " path home" in subvols and " path root" in subvols
            sh("mount", "-o", "subvol=home", root_dev, str(mnt / "home"))
        assert not (mnt / "home" / "liveuser").exists()
        boot = tmp_path / "bootcheck"
        boot.mkdir()
        sh("mount", engine.part_path(loopdisk, 2), str(boot))
        assert (boot / "loader" / "entries").is_dir()
        subprocess.run(["umount", str(boot)], check=False)
        if firmware == "uefi":
            sh("mount", engine.part_path(loopdisk, 1), str(mnt / "boot" / "efi"))
            assert (mnt / "boot" / "efi" / "EFI" / "BOOT" / "BOOTX64.EFI").read_bytes() == b"MZ fake shim"
    finally:
        subprocess.run(["umount", "-R", str(mnt)], check=False)
        if encrypt:
            subprocess.run(["cryptsetup", "close", "luks-check"], check=False)

    # the engine cleaned up after itself
    assert not os.path.ismount(tmp_path / "target")
    assert events[-1]["type"] == "progress"


def test_luks_header_and_passphrase(tmp_path: Path, loopdisk: str) -> None:
    """The exact luksFormat call the engine makes, verified without device-mapper."""
    plan = Plan(disk=loopdisk, firmware="uefi", encrypt=True, passphrase="loop test passphrase")
    runner = engine.Runner(tmp_path / "install.log")
    eng = engine.Engine(plan, runner, target=tmp_path / "target", live_root=tmp_path)
    eng.step_partition()
    runner.run(["cryptsetup", "luksFormat", "--type", "luks2", "--batch-mode", "--key-file=-",
                eng.lay.root_part], input_text=plan.passphrase, secret=True)
    dump = sh("cryptsetup", "luksDump", eng.lay.root_part)
    assert re.search(r"Version:\s+2", dump), dump
    ok = subprocess.run(["cryptsetup", "open", "--test-passphrase", "--key-file=-", eng.lay.root_part],
                        input=plan.passphrase, text=True, capture_output=True, check=False)
    bad = subprocess.run(["cryptsetup", "open", "--test-passphrase", "--key-file=-", eng.lay.root_part],
                         input="wrong passphrase", text=True, capture_output=True, check=False)
    assert ok.returncode == 0 and bad.returncode != 0
    assert plan.passphrase not in (tmp_path / "install.log").read_text()
