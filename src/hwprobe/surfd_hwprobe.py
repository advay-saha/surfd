#!/usr/bin/python3 -sP
"""surfd-hwprobe — look at this machine and suggest drivers/firmware.

It only reads /sys, /proc and the kernel log, and prints suggestions with
the exact commands to run. It never installs anything by itself.

    surfd-hwprobe            human-readable report
    surfd-hwprobe --json     machine-readable
    surfd-hwprobe --sysroot DIR   read DIR/sys and DIR/proc (for tests)
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

RPMFUSION = (
    "sudo dnf install "
    "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm "
    "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm"
)

# Broadcom PCI Wi-Fi chips that need the proprietary "wl" driver (no
# brcmfmac/b43 support upstream).
BROADCOM_WL_ONLY = {"4311", "4312", "4313", "4315", "4328", "4329", "432a", "432b", "432c",
                    "432d", "4331", "4353", "4357", "4358", "4359", "4365", "43a0", "43b1"}
# Intel IPU6/IPU7 MIPI cameras: limited open-source support.
INTEL_IPU = {"9a19", "9a39", "465d", "462e", "a75d", "7d19", "645d", "b05d"}
FINGERPRINT_USB_VENDORS = {"06cb": "Synaptics", "27c6": "Goodix", "138a": "Validity", "2808": "FocalTech",
                           "04f3": "Elan", "1c7a": "LighTuning", "298d": "Next Biometrics"}
VM_HINTS = {
    "QEMU": ("qemu-guest-agent spice-vdagent", "QEMU/KVM guest"),
    "KVM": ("qemu-guest-agent spice-vdagent", "QEMU/KVM guest"),
    "VirtualBox": ("virtualbox-guest-additions", "VirtualBox guest"),
    "VMware": ("open-vm-tools-desktop", "VMware guest"),
    "Microsoft Corporation": ("hyperv-daemons", "Hyper-V guest"),
}


@dataclass
class PciDevice:
    slot: str
    vendor: str
    device: str
    cls: str
    driver: str


@dataclass
class Finding:
    level: str  # "ok" | "suggest" | "warn" | "info"
    title: str
    detail: str = ""
    commands: list[str] = field(default_factory=list)


class Probe:
    def __init__(self, sysroot: Path = Path("/")) -> None:
        self.root = sysroot
        self.findings: list[Finding] = []

    # ------------------------------------------------------------- reading --
    def p(self, path: str) -> Path:
        return self.root / path.lstrip("/")

    def read(self, path: str, default: str = "") -> str:
        try:
            return self.p(path).read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return default

    def pci(self) -> list[PciDevice]:
        base = self.p("/sys/bus/pci/devices")
        out = []
        if not base.is_dir():
            return out
        for dev in sorted(base.iterdir()):
            def rd(name: str, dev: Path = dev) -> str:
                try:
                    return (dev / name).read_text().strip().lower().removeprefix("0x")
                except OSError:
                    return ""
            drv = dev / "driver"
            driver = os.path.basename(os.readlink(drv)) if drv.is_symlink() else ""
            out.append(PciDevice(dev.name, rd("vendor"), rd("device"), rd("class"), driver))
        return out

    def usb_vendors(self) -> set[tuple[str, str]]:
        base = self.p("/sys/bus/usb/devices")
        result = set()
        if base.is_dir():
            for dev in base.iterdir():
                v = dev / "idVendor"
                if v.is_file():
                    result.add((v.read_text().strip().lower(), (dev / "idProduct").read_text().strip().lower()
                                if (dev / "idProduct").is_file() else ""))
        return result

    def modules(self) -> set[str]:
        text = self.read("/proc/modules")
        return {line.split()[0] for line in text.splitlines() if line.strip()}

    def secure_boot(self) -> bool | None:
        vars_dir = self.p("/sys/firmware/efi/efivars")
        if not self.p("/sys/firmware/efi").is_dir():
            return None  # legacy BIOS boot
        for f in vars_dir.glob("SecureBoot-*") if vars_dir.is_dir() else []:
            try:
                data = f.read_bytes()
                return bool(data and data[-1] == 1)
            except OSError:
                return None
        return None

    def kernel_log(self) -> str:
        override = self.p("/var/log/surfd-hwprobe-kmsg")  # test hook
        if override.is_file():
            return override.read_text(errors="replace")
        if self.root != Path("/"):
            return ""
        for cmd in (["journalctl", "-k", "-b", "--no-pager", "-q"], ["dmesg"]):
            if shutil.which(cmd[0]):
                r = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if r.returncode == 0 and r.stdout:
                    return r.stdout
        return ""

    def has_firmware(self, pattern: str) -> bool:
        for d in ("/usr/lib/firmware", "/lib/firmware"):
            base = self.p(d)
            if base.is_dir() and any(base.glob(pattern)):
                return True
        return False

    # ------------------------------------------------------------- probing --
    def add(self, *args: object, **kw: object) -> None:
        self.findings.append(Finding(*args, **kw))  # type: ignore[arg-type]

    def run(self) -> dict[str, object]:
        devices = self.pci()
        arch = self.read("/proc/sys/kernel/arch") or platform.machine()
        sb = self.secure_boot()
        vendor = self.read("/sys/class/dmi/id/sys_vendor")
        product = self.read("/sys/class/dmi/id/product_name")
        model = self.read("/proc/device-tree/model").rstrip("\x00")

        self.check_gpus(devices, sb)
        self.check_wifi(devices, sb)
        self.check_audio(devices)
        self.check_cameras(devices)
        self.check_usb()
        self.check_firmware_log()
        self.check_platform(vendor, product, model, arch)
        if sb:
            self.add("info", "Secure Boot is on",
                     "Fedora's kernel and drivers are signed and work as-is. Third-party kernel modules "
                     "(NVIDIA, broadcom-wl) built by akmods must be signed with a key you enroll once.",
                     ["sudo dnf install akmods mokutil", "sudo kmodgenca -a", "sudo mokutil --import /etc/pki/akmods/certs/public_key.der",
                      "# reboot and choose 'Enroll MOK' in the blue screen"])
        if not devices:
            self.add("warn", "No PCI devices visible",
                     "Running in a container or a sandbox without /sys access? Run surfd-hwprobe on the real machine.")
        elif not any(f.level in ("suggest", "warn") for f in self.findings):
            self.add("ok", "No extra drivers needed", "Everything detected is supported by the installed kernel and firmware.")
        return {
            "machine": {"vendor": vendor, "product": product or model, "arch": arch,
                        "kernel": platform.release() if self.root == Path("/") else "",
                        "secure_boot": sb},
            "findings": [asdict(f) for f in self.findings],
        }

    def check_gpus(self, devices: list[PciDevice], sb: bool | None) -> None:
        gpus = [d for d in devices if d.cls.startswith("03")]
        for g in gpus:
            if g.vendor == "10de":
                if g.driver == "nvidia":
                    self.add("ok", "NVIDIA GPU — proprietary driver loaded",
                             "surfd starts Sway with --unsupported-gpu automatically on this driver.")
                else:
                    self.add("suggest", f"NVIDIA GPU {g.device} (driver: {g.driver or 'none'})",
                             "The open nouveau driver works for basic use. For full performance and power "
                             "management install NVIDIA's driver from RPM Fusion. Sway runs on it with "
                             "--unsupported-gpu, which surfd adds automatically." +
                             (" Secure Boot is on: see the MOK note below." if sb else ""),
                             [RPMFUSION, "sudo dnf install akmod-nvidia",
                              "sudo grubby --update-kernel=ALL --args='nvidia-drm.modeset=1 nvidia-drm.fbdev=1'",
                              "# wait ~5 minutes for the module to build (modinfo -F version nvidia), then reboot"])
            elif g.vendor == "1002":
                self.add("ok" if g.driver == "amdgpu" else "warn",
                         f"AMD GPU (driver: {g.driver or 'none'})",
                         "Mesa's radeonsi/RADV drivers are included." if g.driver == "amdgpu" else
                         "No kernel driver is bound; very old Radeon cards use 'radeon' with limited Vulkan support.")
                self.add("suggest", "AMD hardware video decoding (H.264/HEVC)",
                         "Fedora's Mesa omits patent-encumbered codecs. RPM Fusion's build restores them.",
                         [RPMFUSION, "sudo dnf install mesa-va-drivers-freeworld"])
            elif g.vendor == "8086":
                self.add("ok", f"Intel GPU (driver: {g.driver or 'none'})",
                         "Supported by Mesa (iris/ANV). Hardware video decoding uses libva-intel-media-driver.")
                self.add("suggest", "Intel full codec support (optional)",
                         "Fedora's Intel media driver lacks some patent-encumbered codecs; RPM Fusion has the full one.",
                         [RPMFUSION, "sudo dnf swap libva-intel-media-driver intel-media-driver --allowerasing"])
            elif g.vendor in ("1af4", "1234", "15ad", "80ee", "1b36"):
                self.add("ok", f"Virtual GPU ({g.driver or 'no driver'})", "Fine for testing; use virtio-gpu with 3D for best results.")
        if len([g for g in gpus if g.vendor in ("10de", "1002", "8086")]) > 1:
            self.add("info", "Hybrid graphics detected",
                     "Sway renders on the integrated GPU. Run a program on the discrete GPU with "
                     "DRI_PRIME=1 (AMD/nouveau) or the NVIDIA PRIME variables "
                     "(__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia).")

    def check_wifi(self, devices: list[PciDevice], sb: bool | None) -> None:
        wifi = [d for d in devices if d.cls.startswith("0280")]
        for w in wifi:
            if w.vendor == "14e4":
                if w.device in BROADCOM_WL_ONLY and w.driver != "wl":
                    self.add("suggest", f"Broadcom Wi-Fi {w.device} needs the 'wl' driver",
                             "This chip has no open driver. Connect with Ethernet or USB tethering first.",
                             [RPMFUSION, "sudo dnf install broadcom-wl akmod-wl", "# reboot (Secure Boot: see MOK note)"])
                elif not w.driver:
                    self.add("warn", f"Broadcom Wi-Fi {w.device}: no driver bound",
                             "Check that brcmfmac-firmware is installed: sudo dnf install brcmfmac-firmware")
                else:
                    self.add("ok", f"Broadcom Wi-Fi ({w.driver})")
            elif not w.driver:
                self.add("warn", f"Wi-Fi device {w.vendor}:{w.device} has no driver",
                         "It may be too new for this kernel, or need firmware. See 'Missing firmware' below if listed, "
                         "or try the mainline kernel (docs/hardware.md#mainline-kernel).")
            else:
                self.add("ok", f"Wi-Fi ({w.driver})")

    def check_audio(self, devices: list[PciDevice]) -> None:
        audio = [d for d in devices if d.cls.startswith("0401") or d.cls.startswith("0403")]
        for a in audio:
            if "sof" in a.driver or "snd_sof" in a.driver:
                if self.has_firmware("intel/sof*"):
                    self.add("ok", "Intel SOF audio with firmware installed")
                else:
                    self.add("suggest", "Intel SOF audio firmware missing",
                             "Laptop speakers and microphones on this chip need SOF firmware and UCM profiles.",
                             ["sudo dnf install alsa-sof-firmware alsa-ucm", "# reboot"])
            elif a.driver == "" and a.vendor == "8086":
                self.add("warn", "Intel audio device without a driver",
                         "Try: sudo dnf install alsa-sof-firmware alsa-ucm, then reboot.")

    def check_cameras(self, devices: list[PciDevice]) -> None:
        for d in devices:
            if d.vendor == "8086" and d.device in INTEL_IPU:
                self.add("warn", "Intel IPU6/IPU7 MIPI camera",
                         "Built-in cameras on many 2021+ Intel laptops have limited open-source support. "
                         "They may work through libcamera on recent kernels; RPM Fusion packages the vendor stack. "
                         "USB webcams work normally.",
                         ["# check: https://rpmfusion.org/Howto/Intel_IPU6 (vendor stack, x86_64 only)"])

    def check_usb(self) -> None:
        vendors = self.usb_vendors()
        seen = set()
        for vid, _pid in vendors:
            if vid in FINGERPRINT_USB_VENDORS and vid not in seen:
                seen.add(vid)
                self.add("suggest", f"{FINGERPRINT_USB_VENDORS[vid]} device (possibly a fingerprint reader)",
                         "Many readers work with fprintd; check the libfprint supported-devices list first.",
                         ["sudo dnf install fprintd fprintd-pam", "fprintd-enroll", "sudo authselect enable-feature with-fingerprint"])
        if ("8087", "0b40") in vendors or any(v == "8087" for v, _ in vendors):
            pass  # Intel Bluetooth: covered by linux-firmware

    def check_firmware_log(self) -> None:
        log = self.kernel_log()
        missing = sorted(set(re.findall(r"(?:Direct firmware load for|failed to load firmware) ([^\s:]+)", log)) |
                         set(re.findall(r"firmware: failed to load ([^\s(]+)", log)))
        if missing:
            self.add("suggest", "Missing firmware reported by the kernel",
                     "These files were requested at boot and not found:\n  " + "\n  ".join(missing),
                     [f"dnf provides '/usr/lib/firmware/{m}*'" for m in missing[:5]] +
                     ["sudo dnf install <package shown above>", "# reboot"])

    def check_platform(self, vendor: str, product: str, model: str, arch: str) -> None:
        for key, (pkgs, what) in VM_HINTS.items():
            if key.lower() in (vendor + " " + product).lower():
                self.add("suggest", f"Running as a {what}",
                         "Guest tools give clipboard sharing, resizing and clean shutdown.",
                         [f"sudo dnf install {pkgs}"])
                break
        if arch in ("aarch64", "arm64"):
            if "Raspberry Pi" in model:
                self.add("warn", model, "Raspberry Pi 4/5 boot via UEFI firmware or Fedora's ARM images; "
                         "surfd's ISO targets UEFI/SystemReady machines. See docs/hardware.md#arm.")
            if "Apple" in model or "Apple" in vendor:
                self.add("warn", "Apple Silicon", "Use Fedora Asahi Remix; surfd does not support Apple Silicon.")


def render(report: dict[str, object]) -> str:
    m = report["machine"]
    assert isinstance(m, dict)
    sb = {True: "on", False: "off", None: "n/a (BIOS)"}[m["secure_boot"]]
    lines = [f"surfd-hwprobe — {m['vendor']} {m['product']}".rstrip(),
             f"  arch {m['arch']}  kernel {m['kernel'] or '?'}  secure boot {sb}", ""]
    marks = {"ok": "✓", "suggest": "→", "warn": "!", "info": "i"}
    findings = report["findings"]
    assert isinstance(findings, list)
    order = {"warn": 0, "suggest": 1, "info": 2, "ok": 3}
    for f in sorted(findings, key=lambda f: order[f["level"]]):
        lines.append(f"{marks[f['level']]} {f['title']}")
        if f["detail"]:
            lines += ["    " + line for line in f["detail"].splitlines()]
        for c in f["commands"]:
            lines.append(f"      {c}")
        lines.append("")
    lines.append("Nothing was installed. Hardware notes: /usr/share/doc/surfd-hwprobe/hardware.md")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="surfd-hwprobe", description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--sysroot", type=Path, default=Path("/"), help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    report = Probe(args.sysroot).run()
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
