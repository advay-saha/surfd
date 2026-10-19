"""surfd-hwprobe against fake /sys trees."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import surfd_hwprobe as hw


def make_pci(root: Path, slot: str, vendor: str, device: str, cls: str, driver: str = "") -> None:  # noqa: PLR0917
    d = root / "sys/bus/pci/devices" / slot
    d.mkdir(parents=True)
    (d / "vendor").write_text(f"0x{vendor}\n")
    (d / "device").write_text(f"0x{device}\n")
    (d / "class").write_text(f"0x{cls}\n")
    if driver:
        target = root / "sys/bus/pci/drivers" / driver
        target.mkdir(parents=True, exist_ok=True)
        os.symlink(target, d / "driver")


def titles(root: Path) -> dict[str, str]:
    report = hw.Probe(root).run()
    return {f["title"]: f["level"] for f in report["findings"]}


def test_nvidia_on_nouveau_suggests_rpmfusion(tmp_path: Path) -> None:
    make_pci(tmp_path, "0000:01:00.0", "10de", "2684", "030000", "nouveau")
    t = titles(tmp_path)
    assert t["NVIDIA GPU 2684 (driver: nouveau)"] == "suggest"
    report = hw.Probe(tmp_path).run()
    cmds = [c for f in report["findings"] for c in f["commands"]]
    assert "sudo dnf install akmod-nvidia" in cmds


def test_broadcom_wl_only_chip(tmp_path: Path) -> None:
    make_pci(tmp_path, "0000:02:00.0", "14e4", "43a0", "028000")
    assert titles(tmp_path)["Broadcom Wi-Fi 43a0 needs the 'wl' driver"] == "suggest"


def test_supported_broadcom_ok(tmp_path: Path) -> None:
    make_pci(tmp_path, "0000:02:00.0", "14e4", "43ba", "028000", "brcmfmac")
    assert titles(tmp_path)["Broadcom Wi-Fi (brcmfmac)"] == "ok"


def test_sof_audio_without_firmware(tmp_path: Path) -> None:
    make_pci(tmp_path, "0000:00:1f.3", "8086", "51c8", "040100", "sof-audio-pci-intel-tgl")
    assert titles(tmp_path)["Intel SOF audio firmware missing"] == "suggest"
    (tmp_path / "usr/lib/firmware/intel/sof").mkdir(parents=True)
    assert titles(tmp_path)["Intel SOF audio with firmware installed"] == "ok"


def test_missing_firmware_from_kernel_log(tmp_path: Path) -> None:
    log = tmp_path / "var/log/surfd-hwprobe-kmsg"
    log.parent.mkdir(parents=True)
    log.write_text("iwlwifi 0000:00:14.3: Direct firmware load for iwlwifi-gl-c0-fm-c0-92.ucode failed with error -2\n")
    report = hw.Probe(tmp_path).run()
    f = next(f for f in report["findings"] if f["title"] == "Missing firmware reported by the kernel")
    assert "iwlwifi-gl-c0-fm-c0-92.ucode" in f["detail"]


def test_vm_and_hybrid(tmp_path: Path) -> None:
    dmi = tmp_path / "sys/class/dmi/id"
    dmi.mkdir(parents=True)
    (dmi / "sys_vendor").write_text("QEMU\n")
    (dmi / "product_name").write_text("Standard PC (Q35 + ICH9, 2009)\n")
    make_pci(tmp_path, "0000:00:02.0", "8086", "46a6", "030000", "i915")
    make_pci(tmp_path, "0000:01:00.0", "1002", "73df", "030000", "amdgpu")
    t = titles(tmp_path)
    assert t["Running as a QEMU/KVM guest"] == "suggest"
    assert t["Hybrid graphics detected"] == "info"


def test_clean_machine(tmp_path: Path) -> None:
    make_pci(tmp_path, "0000:00:01.0", "1af4", "1050", "030000", "virtio-pci")
    assert "No extra drivers needed" in titles(tmp_path)


def test_render_and_json(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    make_pci(tmp_path, "0000:02:00.0", "14e4", "4331", "028000")
    assert hw.main(["--sysroot", str(tmp_path)]) == 0
    assert "broadcom-wl" in capsys.readouterr().out
    assert hw.main(["--sysroot", str(tmp_path), "--json"]) == 0
    assert '"findings"' in capsys.readouterr().out
