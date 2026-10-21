# Testing surfd

## Automated (any Linux machine)

```sh
make check            # shellcheck, ruff, ksvalidator, desktop/AppStream validation, ~150 tests
make rpm-test         # build all RPMs with rpmbuild (non-Fedora hosts)
make screenshots      # run the real session + GUI + installer headless and save screenshots
sudo python3 -m pytest src/installer/tests   # adds the real loop-device install test
```

What the tests cover:

- **surfctl**: config merge/validation, comment-preserving edits, reset and
  restore, theme install/export (including path-traversal protection), key
  binding compilation, every CLI command end to end.
- **Generators**: the generated Sway config is validated by real
  `sway --validate` for every theme × variant × tiling/floating;
  `foot --check-config`; Waybar JSON; INI files; GTK 3/4 and login-screen CSS
  through GTK's own parser.
- **Themes**: WCAG contrast thresholds for all built-in palettes.
- **hwprobe**: NVIDIA, Broadcom, SOF audio, missing firmware, VMs, hybrid
  graphics against fake `/sys` trees.
- **GUI**: `tools/gui-screenshot.sh` opens every Surf Settings page and the
  Welcome app in a headless Sway session and runs `src/settings/tests/gui_smoke.py`,
  which clicks a theme card and an accent swatch, changes gaps, tries an
  invalid value, resets and restores, checking surfd.toml and the generated
  files after each step.

On Fedora, also run `./build.sh rpms` (real macros, `%check` runs the tests)
and `./build.sh check` (all kickstart packages exist).

## Boot the ISO in QEMU

UEFI (recommended; matches most hardware):

```sh
sudo dnf install qemu-kvm edk2-ovmf
cp /usr/share/edk2/ovmf/OVMF_VARS.fd /tmp/surfd-vars.fd
qemu-img create -f qcow2 /tmp/surfd.qcow2 30G
qemu-system-x86_64 -enable-kvm -machine q35 -cpu host -smp 4 -m 4096 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/ovmf/OVMF_CODE.fd \
  -drive if=pflash,format=raw,file=/tmp/surfd-vars.fd \
  -device virtio-vga-gl -display gtk,gl=on \
  -device virtio-net-pci,netdev=n0 -netdev user,id=n0 \
  -device intel-hda -device hda-duplex \
  -drive file=/tmp/surfd.qcow2,if=virtio \
  -cdrom out/iso/surfd-0.2.0-f44-x86_64.iso -boot d
```

BIOS: drop the two `pflash` lines. Secure Boot: use `OVMF_CODE.secboot.fd`
and `OVMF_VARS.secboot.fd`. Without 3D, replace the display lines with
`-vga virtio -display gtk` (Sway then renders with pixman; slower but fine).

aarch64 (on an aarch64 host):

```sh
qemu-system-aarch64 -enable-kvm -machine virt -cpu host -smp 4 -m 4096 \
  -bios /usr/share/edk2/aarch64/QEMU_EFI.fd \
  -device virtio-gpu-pci -display gtk -device qemu-xhci -device usb-kbd -device usb-tablet \
  -drive file=/tmp/surfd-arm.qcow2,if=virtio -cdrom out/iso/surfd-0.2.0-f44-aarch64.iso
```

### virt-manager

New VM → Local install media → the ISO → OS: "Fedora Linux 44" → 4 GB RAM,
2+ CPUs → before finishing, *Customize*: Overview → Firmware **UEFI**; Video
**Virtio** with **3D acceleration**; Display Spice **OpenGL** on.

## VM test checklist

Copy into the release PR and tick each line.

**Live session**
- [ ] Boot menu shows "surfd", Plymouth splash shows the S logo and spinner
- [ ] Logs straight into the desktop as *liveuser* (no password)
- [ ] Welcome opens on the "You are running the live system" page; *Install surfd* starts Anaconda
- [ ] `getenforce` → `Enforcing`; `sudo ausearch -m avc -ts boot` → no denials
- [ ] `cat /etc/os-release` → `ID=surfd`, `ID_LIKE=fedora`, `VERSION_ID=44`
- [ ] `rpm -qa | grep -Ei '^fedora-(logos|release)'` → nothing

### Install with Surf Installer

Do each of these at least once, in a fresh VM disk each time:

- [ ] **UEFI, no encryption**: Welcome → *Install surfd* → defaults → pick the VM disk → account → install → *Restart now*
- [ ] **UEFI, encrypted**: same, with *Encrypt the disk*; the passphrase prompt appears at boot (Plymouth) and unlocks
- [ ] **UEFI + Secure Boot** (OVMF `secboot` / Hyper-V Gen 2 / VirtualBox "Secure Boot"): boots to the login screen
- [ ] **Legacy BIOS** (VM firmware set to BIOS): boots via GRUB
- [ ] Keyboard layout chosen in the installer is used at the login screen and on the desktop
- [ ] Wrong inputs are refused: short passphrase, mismatched passwords, username "root"
- [ ] The live USB/ISO disk is not offered in the disk list (real hardware)
- [ ] After install: `getenforce` → Enforcing; `sudo ausearch -m avc -ts boot` → no denials; `rpm -q surfd-live surfd-installer` → not installed; `efibootmgr` lists "surfd" (UEFI)
- [ ] Wi-Fi joined in the live session is remembered on the installed system
- [ ] If something fails, the error page offers the log (`~/surf-installer.log`) and Fedora's installer

### Install with Fedora's installer (advanced path)

- [ ] *Dual boot or custom partitions…* opens Anaconda with surfd branding (sidebar art)
- [ ] Install with automatic partitioning, user with administrator rights
- [ ] Installed system: no `liveuser`, `/etc/sudoers.d/surfd-live` absent, `rpm -q surfd-live` not installed
- [ ] Login screen (greetd + gtkgreet) is themed; login works; wrong password is refused
- [ ] `systemctl status greetd` clean; `journalctl -b -u greetd` free of SELinux errors

**Desktop**
- [ ] Bar, wallpaper, notifications, launcher (**Super + Space**) themed consistently
- [ ] **Super + /** cheat sheet opens; choosing an entry runs it
- [ ] `surfctl theme set kelp --variant light` changes everything live (bar, terminal on next open, GTK apps)
- [ ] `surfctl accent '#e88bc4'`; `surfctl wallpaper set …`; `surfctl bar preset classic`; `surfctl mode floating`
- [ ] Surf Settings: change theme, accent, gaps, bar position; reset and restore
- [ ] Break the config on purpose (`echo 'gaps_inner = "x"' >> ~/.config/surfd/surfd.toml`), log out and in: desktop still starts, notification explains, `surfctl reset --yes` fixes it
- [ ] Firefox, Thunar, foot, pavucontrol, blueman, system-config-printer start
- [ ] Audio plays (PipeWire), volume keys work, also on the lock screen
- [ ] `flatpak remotes` shows *flathub*; `flatpak install flathub org.gnome.Calculator` works
- [ ] `sudo dnf install htop` works (and pulls no weak deps)
- [ ] Screenshots (**Print**, **Shift + Print**) saved to ~/Pictures/Screenshots and the clipboard
- [ ] Lock (**Super + Esc**) and unlock; idle lock after 5 min
- [ ] Volume, brightness and Caps Lock keys show a flyout at the bottom; holding a key updates one flyout
- [ ] **Super + Alt + Space** opens the surfd menu; every sub-menu opens; an entry from each runs
- [ ] **Super + Ctrl + D**: do not disturb holds `notify-send test` back; switching it off shows it
- [ ] **Super + V** lists copied text; **Super + .** types an emoji; **Alt + Tab** switches windows
- [ ] **Ctrl + Print** (window), **Super + Ctrl + Shift + S** (annotate), **Alt + Print** twice (recording saved as .webm, bar shows ● rec)
- [ ] **Super + Shift + Return** drop-down terminal; **Super + Ctrl + N** night light; **Super + Alt + P** power profile
- [ ] Three windows tile as a spiral (auto-tiling); a USB stick mounts with a notification
- [ ] Surf Settings, Welcome and the installer use the surfd look (monospace headings, theme colours)
- [ ] Suspend/resume (VM: `systemctl suspend`)

**Budgets**
- [ ] ISO size `< 1.5 GiB` (`ls -lh`; `sudo tools/iso-size-report.sh <iso>` if over)
- [ ] Idle RAM after login: `tools/measure-ram.sh 120` → `< 400 MiB` on the **installed** system, no apps open
      (the live session uses more, because the overlay lives in RAM)

## Real hardware checklist

For each machine, record: vendor/model, CPU, GPU(s), Wi-Fi chip, Secure Boot
on/off, and attach `surfd-hwprobe --json`.

- [ ] Boots from USB (write with `sudo dd if=surfd.iso of=/dev/sdX bs=4M status=progress oflag=sync` or Fedora Media Writer) in UEFI mode, Secure Boot **on**
- [ ] Display at native resolution; HiDPI: `surfctl set display.scale 1.5`
- [ ] External monitor hotplug; lid close suspends and locks
- [ ] Wi-Fi: scan and connect via the bar's Wi-Fi picker; Bluetooth: pair headphones (blueman)
- [ ] Speakers, headphone jack, internal microphone (laptops with SOF audio especially)
- [ ] Brightness and volume keys; keyboard backlight if present
- [ ] Touchpad: tap to click, two-finger scroll, three-finger workspace swipe
- [ ] Webcam (`gst-launch-1.0 v4l2src ! autovideosink` or a browser test page)
- [ ] Printer: auto-detected network/USB printer prints a test page
- [ ] Suspend/resume ×3; battery drain overnight in suspend
- [ ] `surfd-hwprobe` suggestions are correct for the machine; follow one (e.g. NVIDIA) and confirm it works, including MOK enrollment with Secure Boot
- [ ] `fwupdmgr get-updates` lists the device
- [ ] Idle RAM `tools/measure-ram.sh 120` and battery power draw (`powertop`) noted

## Useful logs

```sh
cat ~/.local/state/surfd/session.log          # this session (surfd-session + Sway)
surfctl doctor
journalctl -b -p warning --no-pager | tail -100
sudo ausearch -m avc -ts boot                 # SELinux denials
```
