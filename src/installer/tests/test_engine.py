"""Installer plan checks, generated files and the exact command sequence (dry run)."""

from __future__ import annotations

from pathlib import Path

import pytest

from surf_installer import disks, engine
from surf_installer.plan import Plan, PlanError, suggest_username


def good_plan(**kw: object) -> Plan:
    base = dict(disk="/dev/nvme0n1", disk_size=256 * 1024**3, fullname="Advay Saha", username="advay",
                password="correct horse", hostname="surfd", timezone="Asia/Kolkata", locale="en_IN.UTF-8",
                keyboard_layout="us", firmware="uefi")
    base.update(kw)
    return Plan(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------------ plan --

def test_good_plan_has_no_problems(tmp_path: Path) -> None:
    (tmp_path / "Asia").mkdir()
    (tmp_path / "Asia" / "Kolkata").write_text("")
    assert good_plan().problems(zoneinfo=tmp_path) == {}


@pytest.mark.parametrize("field,value", [
    ("disk", "sda"), ("disk_size", 8 * 1024**3), ("username", "Advay"), ("username", "root"),
    ("username", "1abc"), ("password", ""), ("password", "a:b"), ("hostname", "my laptop"),
    ("hostname", "-bad"), ("timezone", "Mars/Olympus"), ("timezone", "../etc/passwd"), ("locale", "english"),
    ("keyboard_layout", "US!"),
])
def test_bad_values_are_reported(tmp_path: Path, field: str, value: object) -> None:
    (tmp_path / "Asia").mkdir()
    (tmp_path / "Asia" / "Kolkata").write_text("")
    problems = good_plan(**{field: value}).problems(zoneinfo=tmp_path)
    key = "disk" if field == "disk_size" else field
    assert key in problems, problems


def test_encryption_needs_a_real_passphrase() -> None:
    assert "passphrase" in good_plan(encrypt=True, passphrase="short").problems()
    assert "passphrase" not in good_plan(encrypt=True, passphrase="a long passphrase").problems()


def test_plan_file_is_private_and_consumed(tmp_path: Path) -> None:
    f = tmp_path / "x" / "plan.json"
    good_plan().write(f)
    assert oct(f.stat().st_mode & 0o777) == "0o600"
    plan = Plan.read(f, consume=True)
    assert plan.username == "advay" and not f.exists()
    assert plan.redacted()["password"] == "********"


def test_unknown_plan_fields_rejected(tmp_path: Path) -> None:
    f = tmp_path / "plan.json"
    f.write_text('{"disk": "/dev/sda", "rm_rf": true}')
    with pytest.raises(PlanError):
        Plan.read(f)


@pytest.mark.parametrize("name,expected", [("Advay Saha", "advay"), ("  Zoë  ", "zo"), ("42 Wallaby", "u42")])
def test_suggest_username(name: str, expected: str) -> None:
    assert suggest_username(name) == expected


# ----------------------------------------------------------------- disks --

LSBLK = """{"blockdevices": [
 {"name":"nvme0n1","path":"/dev/nvme0n1","size":512110190592,"type":"disk","model":"Samsung SSD 980","tran":"nvme","rm":false,"ro":false},
 {"name":"sda","path":"/dev/sda","size":31914983424,"type":"disk","model":"Ultra USB 3.0","tran":"usb","rm":true,"ro":false},
 {"name":"sr0","path":"/dev/sr0","size":1400000000,"type":"rom","model":"QEMU DVD","tran":"sata","rm":true,"ro":false},
 {"name":"zram0","path":"/dev/zram0","size":8000000000,"type":"disk","model":null,"tran":null,"rm":false,"ro":false},
 {"name":"vda","path":"/dev/vda","size":34359738368,"type":"disk","model":null,"tran":null,"rm":false,"ro":false},
 {"name":"sdb","path":"/dev/sdb","size":64000000000,"type":"disk","model":"Card","tran":"usb","rm":true,"ro":true}
]}"""


def test_disk_listing_filters_and_labels() -> None:
    found = disks.parse_lsblk(LSBLK, exclude={"/dev/sda"})  # sda is the live USB stick
    assert [d.path for d in found] == ["/dev/nvme0n1", "/dev/vda"]
    assert found[0].subtitle == "512 GB · NVMe SSD · /dev/nvme0n1"
    assert found[1].transport == "virtio" and found[1].title == "vda"


@pytest.mark.parametrize("disk,n,expected", [("/dev/sda", 1, "/dev/sda1"), ("/dev/nvme0n1", 3, "/dev/nvme0n1p3"),
                                              ("/dev/mmcblk0", 2, "/dev/mmcblk0p2"), ("/dev/vda", 2, "/dev/vda2"),
                                              ("/dev/loop7", 1, "/dev/loop7p1")])
def test_partition_paths(disk: str, n: int, expected: str) -> None:
    assert engine.part_path(disk, n) == expected


# ---------------------------------------------------------- file texts --

def layout(uefi: bool = True, encrypted: bool = False) -> engine.Layout:
    lay = engine.Layout.for_disk("/dev/nvme0n1", uefi, encrypted)
    lay.uuids = {"esp": "AAAA-BBBB", "boot": "boot-uuid", "root": "root-uuid", "luks": "luks-uuid"}
    if encrypted:
        lay.luks_name = "luks-luks-uuid"
    return lay


def test_fstab_uefi_and_bios() -> None:
    uefi = engine.fstab_text(layout(True))
    assert "UUID=root-uuid  /          btrfs  subvol=root,compress=zstd:1  0 0" in uefi
    assert "UUID=root-uuid  /home      btrfs  subvol=home" in uefi
    assert "UUID=AAAA-BBBB  /boot/efi  vfat" in uefi
    assert "/boot/efi" not in engine.fstab_text(layout(False))


def test_encryption_texts() -> None:
    lay = layout(True, True)
    assert engine.crypttab_text(lay) == "luks-luks-uuid UUID=luks-uuid none discard\n"
    assert "rd.luks.uuid=luks-luks-uuid" in engine.kernel_cmdline(lay)
    assert "rd.luks.uuid=luks-luks-uuid" in engine.default_grub_text(lay)
    assert engine.crypttab_text(layout(True, False)) == ""


def test_kernel_cmdline_plain() -> None:
    assert engine.kernel_cmdline(layout()) == "root=UUID=root-uuid ro rootflags=subvol=root rhgb quiet"


def test_efi_stub_points_at_boot_partition() -> None:
    stub = engine.efi_grub_stub("boot-uuid")
    assert "--fs-uuid --set=dev boot-uuid" in stub and "configfile $prefix/grub.cfg" in stub


def test_x11_keyboard_conf_roundtrips_with_surfctl(tmp_path: Path) -> None:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "surfctl"))
    from surfd import system
    f = tmp_path / "00-keyboard.conf"
    f.write_text(engine.x11_keyboard_conf("de", "nodeadkeys"))
    assert system.system_keyboard(f, tmp_path / "none") == {"layout": "de", "variant": "nodeadkeys"}


@pytest.mark.parametrize("machine,expected", [("x86_64", ("shimx64.efi", "BOOTX64.EFI")),
                                               ("aarch64", ("shimaa64.efi", "BOOTAA64.EFI"))])
def test_efi_names(machine: str, expected: tuple[str, str]) -> None:
    assert engine.efi_names(machine) == expected


# ------------------------------------------------------ dry-run sequence --

def dry_run(tmp_path: Path, **kw: object) -> tuple[list[list[str]], list[dict[str, object]]]:
    events: list[dict[str, object]] = []
    runner = engine.Runner(tmp_path / "log.txt", dry_run=True)
    eng = engine.Engine(good_plan(source=str(tmp_path / "src"), **kw), runner, target=tmp_path / "target",
                        emit=events.append, live_root=tmp_path / "live")
    eng.plan.check = lambda: None  # type: ignore[method-assign]  # zoneinfo may be absent on the test host
    eng.install()
    return runner.commands, events


def flat(cmds: list[list[str]]) -> list[str]:
    return [" ".join(c) for c in cmds]


def test_dry_run_uefi_plain(tmp_path: Path) -> None:
    cmds, events = dry_run(tmp_path)
    text = flat(cmds)
    assert any(c.startswith("sgdisk -n1:0:+600M -t1:EF00") for c in text)
    assert "mkfs.vfat -F 32 -n EFI /dev/nvme0n1p1" in text
    assert "mkfs.btrfs -f -q -L surfd /dev/nvme0n1p3" in text
    assert not any("cryptsetup" in c for c in text)
    assert any(c.startswith("rsync -aHAXx") and "--exclude=/boot/efi/*" in c for c in text)
    assert any("kernel-install add KVER /lib/modules/KVER/vmlinuz" in c for c in text)
    assert any("efibootmgr --create --disk /dev/nvme0n1 --part 1 --label surfd" in c for c in text)
    assert not any("grub2-install" in c for c in text)
    assert any(c.startswith("setfiles -F -r") for c in text)
    # order: partition < format < copy < users < bootloader
    idx = {k: next(i for i, c in enumerate(text) if c.startswith(k))
           for k in ("sgdisk --zap-all", "mkfs.btrfs", "rsync -aHAXx", "chroot", "setfiles")}
    assert idx["sgdisk --zap-all"] < idx["mkfs.btrfs"] < idx["rsync -aHAXx"] < idx["chroot"] < idx["setfiles"]
    fractions = [e["fraction"] for e in events if e["type"] == "progress"]
    assert fractions == sorted(fractions) and fractions[-1] == pytest.approx(1.0, abs=0.001)


def test_dry_run_bios_encrypted(tmp_path: Path) -> None:
    cmds, _ = dry_run(tmp_path, firmware="bios", encrypt=True, passphrase="a long passphrase")
    text = flat(cmds)
    assert any(c.startswith("sgdisk -n1:0:+1M -t1:EF02") for c in text)
    assert not any("mkfs.vfat" in c for c in text)
    assert "cryptsetup luksFormat --type luks2 --batch-mode --key-file=- /dev/nvme0n1p3" in text
    assert "mkfs.btrfs -f -q -L surfd /dev/mapper/luks-LUKS-UUID" in text
    assert any(c.endswith("grub2-install --target=i386-pc /dev/nvme0n1") for c in text)
    assert "cryptsetup close luks-LUKS-UUID" in text


def test_secrets_never_reach_the_log(tmp_path: Path) -> None:
    dry_run(tmp_path, encrypt=True, passphrase="SuperSecretPhrase", password="TopSecretPw")
    log = (tmp_path / "log.txt").read_text()
    assert "SuperSecretPhrase" not in log and "TopSecretPw" not in log


def test_engine_cli_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import json
    plan_file = tmp_path / "plan.json"
    good_plan(timezone="UTC").write(plan_file)
    rc = engine.main(["--plan", str(plan_file), "--dry-run", "--keep-plan", "--log", str(tmp_path / "l"),
                      "--source", str(tmp_path), "--target", str(tmp_path / "t")])
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert rc == 0 and events[-1]["type"] == "done"
    assert any(e["type"] == "command" for e in events)
