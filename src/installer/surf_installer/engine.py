"""The surfd install engine. Runs as root; the wizard talks to it via JSON lines.

    surf-installer-engine --plan /run/user/1000/surf-installer/plan.json
    surf-installer-engine --plan plan.json --dry-run          # print, change nothing
    surf-installer-engine --plan plan.json --only partition,format,mount,copy,fstab --source /tmp/root

What it does (the "erase one disk" install):

  1. partition   GPT: [EFI 600 MiB | BIOS boot 1 MiB] + /boot 1 GiB ext4 + root
  2. encrypt     optional LUKS2 around root
  3. format      vfat (EFI), ext4 (/boot), btrfs with "root" and "home" subvolumes (or ext4)
  4. mount       everything under the target directory
  5. copy        the pristine live root (/run/rootfsbase) with rsync
  6. fstab       fstab, crypttab, kernel command line, /etc/default/grub
  7. configure   hostname, locale, keyboard, time zone, machine-id, Wi-Fi from the live session,
                 live-only bits removed
  8. users       your account (administrator), root locked
  9. bootloader  kernel-install (initramfs + boot entries), GRUB (shim on UEFI), firmware boot entry
 10. selinux     relabel the new system
 11. finish      unmount and close

Fedora's full installer (Anaconda) remains available for anything else:
dual boot, existing partitions, RAID, LVM.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .plan import Plan, PlanError

ESP_SIZE = "+600M"
BOOT_SIZE = "+1G"
BTRFS_OPTS = "compress=zstd:1"
RSYNC_EXCLUDES = [
    "/dev/*", "/proc/*", "/sys/*", "/run/*", "/tmp/*", "/var/tmp/*", "/mnt/*", "/media/*",
    "/boot/efi/*", "/boot/initramfs-*", "/boot/loader/entries/*", "/home/liveuser",
    "/etc/sudoers.d/surfd-live", "/var/log/journal/*", "/var/cache/dnf/*", "/.autorelabel",
]
LIVE_PACKAGES = ["surfd-live", "surfd-installer"]

STEPS: list[tuple[str, str, float]] = [
    ("partition", "Preparing the disk", 0.03),
    ("encrypt", "Setting up encryption", 0.03),
    ("format", "Creating file systems", 0.03),
    ("mount", "Mounting", 0.01),
    ("copy", "Copying surfd to the disk", 0.62),
    ("fstab", "Writing the file system table", 0.01),
    ("configure", "Applying your settings", 0.03),
    ("users", "Creating your account", 0.02),
    ("bootloader", "Installing the boot loader", 0.14),
    ("selinux", "Securing files (SELinux labels)", 0.06),
    ("finish", "Finishing", 0.02),
]


class InstallError(RuntimeError):
    pass


def part_path(disk: str, number: int) -> str:
    """/dev/sda + 1 -> /dev/sda1;  /dev/nvme0n1 + 1 -> /dev/nvme0n1p1."""
    return f"{disk}p{number}" if disk[-1].isdigit() else f"{disk}{number}"


def efi_names(machine: str) -> tuple[str, str]:
    """(shim file, fallback file) for this CPU architecture."""
    if machine in ("aarch64", "arm64"):
        return "shimaa64.efi", "BOOTAA64.EFI"
    return "shimx64.efi", "BOOTX64.EFI"


# ---------------------------------------------------------------- texts ----

@dataclass
class Layout:
    disk: str
    uefi: bool
    encrypted: bool
    root_fs: str = "btrfs"
    esp: str = ""
    boot: str = ""
    root_part: str = ""
    root_dev: str = ""  # /dev/mapper/luks-… when encrypted
    luks_name: str = ""
    uuids: dict[str, str] = field(default_factory=dict)  # esp, boot, root (btrfs), luks

    @property
    def btrfs(self) -> bool:
        return self.root_fs == "btrfs"

    @classmethod
    def for_disk(cls, disk: str, uefi: bool, encrypted: bool, root_fs: str = "btrfs") -> Layout:
        lay = cls(disk=disk, uefi=uefi, encrypted=encrypted, root_fs=root_fs)
        lay.esp = part_path(disk, 1) if uefi else ""
        lay.boot = part_path(disk, 2)
        lay.root_part = part_path(disk, 3)
        lay.root_dev = lay.root_part
        return lay


def fstab_text(lay: Layout) -> str:
    u = lay.uuids
    root = (f"UUID={u['root']}  /          btrfs  subvol=root,{BTRFS_OPTS}  0 0" if lay.btrfs
            else f"UUID={u['root']}  /          ext4   defaults  1 1")
    lines = [
        "# /etc/fstab — written by the surfd installer",
        root,
        f"UUID={u['boot']}  /boot      ext4   defaults  1 2",
    ]
    if lay.uefi:
        lines.append(f"UUID={u['esp']}  /boot/efi  vfat   umask=0077,shortname=winnt  0 2")
    if lay.btrfs:
        lines.append(f"UUID={u['root']}  /home      btrfs  subvol=home,{BTRFS_OPTS}  0 0")
    return "\n".join(lines) + "\n"


def crypttab_text(lay: Layout) -> str:
    return f"{lay.luks_name} UUID={lay.uuids['luks']} none discard\n" if lay.encrypted else ""


def kernel_cmdline(lay: Layout) -> str:
    parts = [f"root=UUID={lay.uuids['root']}", "ro"] + (["rootflags=subvol=root"] if lay.btrfs else [])
    if lay.encrypted:
        parts.append(f"rd.luks.uuid={lay.luks_name}")
    parts += ["rhgb", "quiet"]
    return " ".join(parts)


def default_grub_text(lay: Layout) -> str:
    extra = ("rootflags=subvol=root " if lay.btrfs else "") + (f"rd.luks.uuid={lay.luks_name} " if lay.encrypted else "")
    return (
        'GRUB_TIMEOUT=3\n'
        'GRUB_DISTRIBUTOR="surfd"\n'
        'GRUB_DEFAULT=saved\n'
        'GRUB_DISABLE_SUBMENU=true\n'
        'GRUB_TERMINAL_OUTPUT="console"\n'
        f'GRUB_CMDLINE_LINUX="{extra}rhgb quiet"\n'
        'GRUB_DISABLE_RECOVERY="true"\n'
        'GRUB_ENABLE_BLSCFG=true\n'
    )


def efi_grub_stub(boot_uuid: str) -> str:
    """The small grub.cfg on the EFI partition that hands over to /boot/grub2/grub.cfg (as on Fedora)."""
    return (f"search --no-floppy --fs-uuid --set=dev {boot_uuid}\n"
            "set prefix=($dev)/grub2\n"
            "export $prefix\n"
            "configfile $prefix/grub.cfg\n")


def x11_keyboard_conf(layout: str, variant: str) -> str:
    lines = ['# Written by the surfd installer (read by the login screen and surfctl)',
             'Section "InputClass"', '        Identifier "system-keyboard"',
             '        MatchIsKeyboard "on"', f'        Option "XkbLayout" "{layout}"']
    if variant:
        lines.append(f'        Option "XkbVariant" "{variant}"')
    lines.append("EndSection")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------- running ----

class Runner:
    """Runs commands, logs them, or (dry run) only records them."""

    def __init__(self, log: Path, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.log_path = log
        log.parent.mkdir(parents=True, exist_ok=True)
        self.log = log.open("a", encoding="utf-8")
        self.commands: list[list[str]] = []

    def write_log(self, text: str) -> None:
        self.log.write(text if text.endswith("\n") else text + "\n")
        self.log.flush()

    def run(self, cmd: list[str], *, input_text: str | None = None, check: bool = True,
            secret: bool = False) -> str:
        self.commands.append(cmd)
        self.write_log("$ " + shlex.join(cmd) + ("   [stdin: hidden]" if secret and input_text else ""))
        if self.dry_run:
            return self._fake_output(cmd)
        r = subprocess.run(cmd, input=input_text, capture_output=True, text=True, check=False)
        if r.stdout:
            self.write_log(r.stdout)
        if r.stderr:
            self.write_log(r.stderr)
        if check and r.returncode != 0:
            raise InstallError(f"{shlex.join(cmd[:4])}… failed ({r.returncode}): "
                               f"{(r.stderr or r.stdout).strip().splitlines()[-1:] or ''}")
        return r.stdout

    def stream(self, cmd: list[str], on_line: Callable[[str], None]) -> None:
        """Run a long command, feeding each output line (\\r or \\n separated) to on_line."""
        self.commands.append(cmd)
        self.write_log("$ " + shlex.join(cmd))
        if self.dry_run:
            for pct in (10, 50, 100):
                on_line(f"  1,000  {pct}%  1.00MB/s  0:00:01")
            return
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert proc.stdout is not None
        buf = b""
        while chunk := proc.stdout.read(4096):
            buf += chunk
            *lines, buf = re.split(rb"[\r\n]", buf)
            for line in lines:
                if line.strip():
                    on_line(line.decode(errors="replace"))
        rc = proc.wait()
        if rc not in {0, 24}:  # 24 = some source files vanished: harmless on a live system
            raise InstallError(f"{cmd[0]} failed with exit code {rc} (see the log)")

    @staticmethod
    def _fake_output(cmd: list[str]) -> str:
        if cmd[:1] == ["blkid"]:
            return f"UUID-OF-{os.path.basename(cmd[-1]).upper()}\n"
        if cmd[:2] == ["cryptsetup", "luksUUID"]:
            return "LUKS-UUID\n"
        return ""


# ---------------------------------------------------------------- engine ----

class Engine:
    def __init__(self, plan: Plan, runner: Runner, *, target: Path = Path("/mnt/surfd-target"),
                 emit: Callable[[dict[str, object]], None] | None = None, live_root: Path = Path("/")) -> None:
        self.plan = plan
        self.run = runner
        self.target = target
        self.emit = emit or (lambda ev: None)
        self.live_root = live_root  # the running system (for Wi-Fi connections)
        uefi = plan.firmware == "uefi" or (plan.firmware == "auto" and Path("/sys/firmware/efi").is_dir())
        self.lay = Layout.for_disk(plan.disk, uefi, plan.encrypt, plan.root_fs)
        self.machine = platform.machine()
        self.mounted: list[Path] = []
        self.source: Path | None = Path(plan.source) if plan.source else None
        self._done = 0.0
        self.pace = 0.0

    # ------------------------------------------------------------ helpers --
    def t(self, path: str) -> Path:
        return self.target / path.lstrip("/")

    def write(self, path: str, text: str, mode: int = 0o644) -> None:
        self.run.write_log(f"# write {path}:\n{text.rstrip()}" if "password" not in path else f"# write {path}")
        if self.run.dry_run:
            return
        p = self.t(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        os.chmod(p, mode)

    def chroot(self, cmd: list[str], **kw: object) -> str:
        return self.run.run(["chroot", str(self.target), *cmd], **kw)  # type: ignore[arg-type]

    def uuid(self, dev: str) -> str:
        if not self.run.dry_run:
            self.run.run(["udevadm", "settle"], check=False)
        out = self.run.run(["blkid", "-s", "UUID", "-o", "value", dev]).strip()
        if not out:
            raise InstallError(f"could not read the UUID of {dev}")
        return out

    def progress(self, step: str, label: str, fraction: float, detail: str = "") -> None:
        self.emit({"type": "progress", "step": step, "label": label, "fraction": round(min(fraction, 1.0), 4),
                   "detail": detail})

    # -------------------------------------------------------------- steps --
    def step_partition(self) -> None:
        d = self.lay.disk
        if not self.run.dry_run and not Path(d).exists():
            raise InstallError(f"{d} does not exist")
        # Nothing on the target disk may stay mounted or in use.
        self.run.run(["sh", "-c", f"umount -R {shlex.quote(d)}* 2>/dev/null; swapoff {shlex.quote(d)}* 2>/dev/null; true"],
                     check=False)
        self.run.run(["wipefs", "--all", "--force", d])
        self.run.run(["sgdisk", "--zap-all", d])
        first = (["-n1:0:" + ESP_SIZE, "-t1:EF00", "-c1:EFI System"] if self.lay.uefi
                 else ["-n1:0:+1M", "-t1:EF02", "-c1:BIOS boot"])
        self.run.run(["sgdisk", *first, "-n2:0:" + BOOT_SIZE, "-t2:8300", "-c2:boot",
                      "-n3:0:0", "-t3:8300", "-c3:surfd", d])
        self.run.run(["partprobe", d], check=False)
        self.run.run(["udevadm", "settle"], check=False)
        if not self.run.dry_run:
            for _ in range(50):
                if Path(self.lay.root_part).exists():
                    break
                time.sleep(0.1)
            else:
                raise InstallError(f"partition {self.lay.root_part} did not appear")

    def step_encrypt(self) -> None:
        if not self.lay.encrypted:
            return
        key = self.plan.passphrase
        self.run.run(["cryptsetup", "luksFormat", "--type", "luks2", "--batch-mode", "--key-file=-",
                      self.lay.root_part], input_text=key, secret=True)
        luks_uuid = self.run.run(["cryptsetup", "luksUUID", self.lay.root_part]).strip()
        self.lay.uuids["luks"] = luks_uuid
        self.lay.luks_name = f"luks-{luks_uuid}"
        self.run.run(["cryptsetup", "open", "--key-file=-", self.lay.root_part, self.lay.luks_name],
                     input_text=key, secret=True)
        self.lay.root_dev = f"/dev/mapper/{self.lay.luks_name}"

    def step_format(self) -> None:
        if self.lay.uefi:
            self.run.run(["mkfs.vfat", "-F", "32", "-n", "EFI", self.lay.esp])
        self.run.run(["mkfs.ext4", "-F", "-q", "-L", "boot", self.lay.boot])
        if self.lay.btrfs:
            self.run.run(["mkfs.btrfs", "-f", "-q", "-L", "surfd", self.lay.root_dev])
            tmp = Path("/run/surf-installer/btrfs-top")
            if not self.run.dry_run:
                tmp.mkdir(parents=True, exist_ok=True)
            self.run.run(["mount", self.lay.root_dev, str(tmp)])
            try:
                self.run.run(["btrfs", "subvolume", "create", str(tmp / "root")])
                self.run.run(["btrfs", "subvolume", "create", str(tmp / "home")])
            finally:
                self.run.run(["umount", str(tmp)])
        else:
            self.run.run(["mkfs.ext4", "-F", "-q", "-L", "surfd", self.lay.root_dev])
        if self.lay.uefi:
            self.lay.uuids["esp"] = self.uuid(self.lay.esp)
        self.lay.uuids["boot"] = self.uuid(self.lay.boot)
        self.lay.uuids["root"] = self.uuid(self.lay.root_dev)

    def _mount(self, args: list[str], where: Path) -> None:
        if not self.run.dry_run:
            where.mkdir(parents=True, exist_ok=True)
        self.run.run(["mount", *args, str(where)])
        self.mounted.append(where)

    def step_mount(self) -> None:
        if self.lay.btrfs:
            self._mount(["-o", f"subvol=root,{BTRFS_OPTS}", self.lay.root_dev], self.target)
            self._mount(["-o", f"subvol=home,{BTRFS_OPTS}", self.lay.root_dev], self.t("/home"))
        else:
            self._mount([self.lay.root_dev], self.target)
        self._mount([self.lay.boot], self.t("/boot"))
        if self.lay.uefi:
            self._mount([self.lay.esp], self.t("/boot/efi"))

    def find_source(self) -> Path:
        if self.source is not None:
            return self.source
        base = Path("/run/rootfsbase")  # dmsquash-live (overlayfs): the untouched image
        if base.is_dir() and (base / "etc").is_dir():
            return base
        squash = Path("/run/initramfs/live/LiveOS/squashfs.img")
        if squash.is_file():
            sq = Path("/run/surf-installer/squashfs")
            self._mount(["-o", "ro,loop", str(squash)], sq)
            rootfs = sq / "LiveOS" / "rootfs.img"
            if rootfs.is_file():
                root = Path("/run/surf-installer/rootfs")
                self._mount(["-o", "ro,loop", str(rootfs)], root)
                return root
            return sq
        raise InstallError("cannot find the live system image (/run/rootfsbase); are you running the live ISO?")

    def step_copy(self) -> None:
        src = self.find_source()
        label = dict((s, lab) for s, lab, _ in STEPS)["copy"]
        excludes = [f"--exclude={e}" for e in RSYNC_EXCLUDES]

        def on_line(line: str) -> None:
            m = re.search(r"\s(\d{1,3})%", line)
            if m:
                self.progress("copy", label, self._done + STEP_WEIGHT["copy"] * int(m.group(1)) / 100 * 0.97)

        self.run.stream(["rsync", "-aHAXx", "--numeric-ids", "--info=progress2", "--no-inc-recursive",
                         *excludes, f"{src}/", f"{self.target}/"], on_line)
        if self.lay.uefi and (src / "boot" / "efi").is_dir():
            # vfat has no owners, permissions or links
            self.run.run(["rsync", "-rt", "--no-perms", "--no-owner", "--no-group",
                          f"{src}/boot/efi/", f"{self.target}/boot/efi/"])
        for d in ("dev", "proc", "sys", "run", "tmp", "var/tmp", "boot/loader/entries"):
            if not self.run.dry_run:
                self.t(d).mkdir(parents=True, exist_ok=True)
        if not self.run.dry_run:
            os.chmod(self.t("/tmp"), 0o1777)
            os.chmod(self.t("/var/tmp"), 0o1777)

    def step_fstab(self) -> None:
        self.write("/etc/fstab", fstab_text(self.lay))
        if self.lay.encrypted:
            self.write("/etc/crypttab", crypttab_text(self.lay), 0o600)
        self.write("/etc/kernel/cmdline", kernel_cmdline(self.lay) + "\n")
        self.write("/etc/default/grub", default_grub_text(self.lay))

    def _bind_mounts(self) -> None:
        for src in ("/dev", "/dev/pts", "/proc", "/sys", "/run"):
            self._mount(["--bind", src], self.t(src))
        if self.lay.uefi and Path("/sys/firmware/efi/efivars").is_dir():
            self._mount(["-t", "efivarfs", "efivarfs"], self.t("/sys/firmware/efi/efivars"))

    def step_configure(self) -> None:
        p = self.plan
        self._bind_mounts()
        if not self.run.dry_run:
            self.t("/etc/machine-id").unlink(missing_ok=True)
        keymap = p.keyboard_layout.split(",")[0] + (f"-{p.keyboard_variant}" if p.keyboard_variant
                                                    and "," not in p.keyboard_variant else "")
        self.run.run(["systemd-firstboot", f"--root={self.target}", "--force", f"--locale={p.locale}",
                      f"--keymap={keymap}", f"--timezone={p.timezone}", f"--hostname={p.hostname}",
                      "--setup-machine-id"])
        self.write("/etc/X11/xorg.conf.d/00-keyboard.conf", x11_keyboard_conf(p.keyboard_layout, p.keyboard_variant))
        # Keep Wi-Fi networks joined during the live session.
        nm = self.live_root / "etc/NetworkManager/system-connections"
        if nm.is_dir():
            for f in sorted(nm.glob("*.nmconnection")):
                self.run.run(["install", "-D", "-m", "0600", str(f), str(self.t(f"/etc/NetworkManager/system-connections/{f.name}"))])
        # Remove what only belongs on the live medium.
        self.run.run(["systemctl", f"--root={self.target}", "disable", "surfd-livesys.service"], check=False)
        self.run.run(["rm", "-f", str(self.t("/etc/sudoers.d/surfd-live"))])
        self.chroot(["rpm", "-e", "--nodeps", *LIVE_PACKAGES], check=False)
        self.chroot(["systemctl", "set-default", "graphical.target"], check=False)

    def step_users(self) -> None:
        p = self.plan
        self.chroot(["useradd", "--create-home", "--groups", "wheel", "--comment", p.fullname, p.username])
        self.chroot(["chpasswd"], input_text=f"{p.username}:{p.password}\n", secret=True)
        self.chroot(["passwd", "--lock", "root"], check=False)

    def step_bootloader(self) -> None:
        kernels = ["KVER"] if self.run.dry_run else sorted(
            k.name for k in self.t("/lib/modules").iterdir() if (k / "vmlinuz").is_file())
        if not kernels:
            raise InstallError("no kernel found in the copied system")
        for kver in kernels:
            self.chroot(["kernel-install", "add", kver, f"/lib/modules/{kver}/vmlinuz"])
        if self.lay.uefi:
            shim, fallback = efi_names(self.machine)
            self.write("/boot/efi/EFI/fedora/grub.cfg", efi_grub_stub(self.lay.uuids["boot"]), 0o700)
            self.chroot(["grub2-mkconfig", "-o", "/boot/grub2/grub.cfg"])
            if not self.run.dry_run and not self.t(f"/boot/efi/EFI/BOOT/{fallback}").exists():
                self.run.write_log(f"warning: no fallback {fallback}; relying on the firmware boot entry")
            r = self.run.run(["efibootmgr", "--create", "--disk", self.lay.disk, "--part", "1", "--label", "surfd",
                              "--loader", f"\\EFI\\fedora\\{shim}"], check=False)
            if "surfd" not in r and not self.run.dry_run:
                self.run.write_log("warning: could not add a firmware boot entry; the fallback loader will be used")
        else:
            self.chroot(["grub2-install", "--target=i386-pc", self.lay.disk])
            self.chroot(["grub2-mkconfig", "-o", "/boot/grub2/grub.cfg"])

    def step_selinux(self) -> None:
        contexts = "/etc/selinux/targeted/contexts/files/file_contexts"
        if not self.run.dry_run and not self.t(contexts).is_file():
            self.run.write_log("SELinux policy not found in the target; skipping relabel")
            return
        excludes = []
        for d in ("/dev", "/proc", "/sys", "/run"):
            excludes += ["-e", str(self.t(d))]
        try:
            self.run.run(["setfiles", "-F", "-r", str(self.target), *excludes, str(self.t(contexts)), str(self.target)])
        except InstallError:
            # Fall back to relabelling on first boot (slower first start, same result).
            self.write("/.autorelabel", "")

    def step_finish(self) -> None:
        self.run.run(["sync"])
        self.cleanup()

    def cleanup(self) -> None:
        for m in reversed(self.mounted):
            self.run.run(["umount", "-l", str(m)], check=False)
        self.mounted.clear()
        if self.lay.encrypted and self.lay.luks_name:
            self.run.run(["cryptsetup", "close", self.lay.luks_name], check=False)

    # ---------------------------------------------------------------- run --
    def install(self, only: set[str] | None = None) -> None:
        if only is None:
            self.plan.check()
        self.run.write_log("plan: " + json.dumps(self.plan.redacted()))
        self.run.write_log(f"firmware: {'UEFI' if self.lay.uefi else 'BIOS'}  arch: {self.machine}")
        try:
            for name, label, weight in STEPS:
                if only is not None and name not in only:
                    continue
                self.progress(name, label, self._done)
                if self.pace:
                    time.sleep(self.pace)
                getattr(self, f"step_{name}")()
                self._done += weight
                self.progress(name, label, self._done)
        except BaseException:
            self.cleanup()
            raise
        if only is not None and "finish" not in only:
            self.cleanup()


STEP_WEIGHT = {name: weight for name, _, weight in STEPS}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="surf-installer-engine", description=__doc__.split("\n\n")[0])
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true", help="record commands; change nothing")
    ap.add_argument("--only", help="comma-separated steps (testing)")
    ap.add_argument("--source", help="copy from this directory instead of the live image")
    ap.add_argument("--target", type=Path, default=Path("/mnt/surfd-target"))
    ap.add_argument("--log", type=Path, default=Path("/tmp/surf-installer.log"))
    ap.add_argument("--keep-plan", action="store_true", help="do not delete the plan file after reading")
    ap.add_argument("--pace", type=float, default=0.0, help=argparse.SUPPRESS)  # dry-run demos: seconds per step
    args = ap.parse_args(argv)

    def emit(event: dict[str, object]) -> None:
        print(json.dumps(event), flush=True)

    if not args.dry_run and os.geteuid() != 0:
        emit({"type": "error", "message": "the installer engine must run as root"})
        return 1
    try:
        plan = Plan.read(args.plan, consume=not args.keep_plan)
        if args.source:
            plan.source = args.source
        runner = Runner(args.log, dry_run=args.dry_run)
        only = set(args.only.split(",")) if args.only else None
        engine = Engine(plan, runner, target=args.target, emit=emit)
        engine.pace = args.pace if args.dry_run else 0.0
        engine.install(only)
    except (PlanError, InstallError, OSError) as e:
        emit({"type": "error", "message": str(e), "log": str(args.log)})
        return 1
    if args.dry_run:
        for cmd in runner.commands:
            print(json.dumps({"type": "command", "argv": cmd}), flush=True)
    emit({"type": "done", "log": str(args.log)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
