# Hardware notes

surfd uses **Fedora's kernel, firmware and Mesa unchanged**. If Fedora 44
supports a device, surfd does too, and no Linux distribution can promise more
than its kernel and firmware deliver. This page lists what is included, what
needs an extra step, and what does not work.

Start with:

```sh
surfd-hwprobe          # or: Surf Settings → System → Check drivers and firmware
```

It reads `/sys`, `/proc` and the kernel log and prints suggestions with the
exact commands. It never installs anything by itself.

## Included out of the box

| Area | What surfd ships |
|---|---|
| Kernel | Fedora's current stable `kernel`, `kernel-modules`, `kernel-modules-extra` |
| Firmware | `linux-firmware` and Fedora's `@hardware-support` group (Intel/AMD/NVIDIA GPU, Intel/Atheros/Broadcom-FullMAC/MediaTek/Realtek Wi-Fi and Bluetooth), `alsa-sof-firmware` + `alsa-ucm` (laptop audio), CPU microcode (x86_64) |
| Graphics | Mesa: Intel (iris, ANV), AMD (radeonsi, RADV), NVIDIA (nouveau, NVK), virtio, and Arm GPUs (panfrost/panthor, freedreno) — everything Wayland needs. VA-API video decoding (`mesa-va-drivers`, `libva-intel-media-driver`) |
| Audio | PipeWire with PulseAudio/ALSA compatibility, WirePlumber |
| Network | NetworkManager (Wi-Fi, Ethernet, Bluetooth tethering), `nmtui`, a Wi-Fi picker in the bar |
| Printing | CUPS with driverless IPP and IPP-over-USB, system-config-printer |
| Power | power-profiles-daemon, upower, thermald (Intel), zram swap |
| Firmware updates | fwupd (`fwupdmgr get-updates`) |

## Needs one extra step

### NVIDIA (proprietary driver)

The open **nouveau** driver is used by default and is fine for desktop use on
most cards. For gaming, CUDA or better battery life, install NVIDIA's driver
from RPM Fusion:

```sh
sudo dnf install \
  https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
  https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm
sudo dnf install akmod-nvidia
sudo grubby --update-kernel=ALL --args='nvidia-drm.modeset=1 nvidia-drm.fbdev=1'
# wait until `modinfo -F version nvidia` prints a version (the module builds in the background), then reboot
```

Sway refuses to start on this driver unless given `--unsupported-gpu`;
`surfd-session` and the login screen add it automatically when the `nvidia`
module is loaded. Upstream Sway does not support this setup, so report
NVIDIA-only glitches to NVIDIA/RPM Fusion first. Recent drivers (555+) with
explicit sync work much better than older ones.

### Broadcom Wi-Fi that needs `wl`

Some older Broadcom chips (e.g. BCM4331, BCM4352, BCM4360) have no open
driver. Connect by Ethernet or USB tethering, then:

```sh
# (enable RPM Fusion as above)
sudo dnf install broadcom-wl akmod-wl
sudo reboot
```

### Secure Boot and third-party modules

Fedora's shim, GRUB and kernel are signed; Secure Boot works as-is. Kernel
modules built by `akmods` (NVIDIA, `wl`) must be signed with your own key
once:

```sh
sudo dnf install akmods mokutil
sudo kmodgenca -a
sudo mokutil --import /etc/pki/akmods/certs/public_key.der
# set a one-time password, reboot, choose "Enroll MOK" and enter it
```

### Hardware video decoding with all codecs

Fedora's Mesa omits patent-encumbered codecs (H.264/HEVC encode/decode on AMD).

```sh
sudo dnf install mesa-va-drivers-freeworld                                   # AMD
sudo dnf swap libva-intel-media-driver intel-media-driver --allowerasing      # Intel (full codec set)
```

### Virtual machines

`surfd-hwprobe` suggests guest tools: `qemu-guest-agent spice-vdagent`
(QEMU/KVM), `open-vm-tools-desktop` (VMware), `virtualbox-guest-additions`,
`hyperv-daemons`.

### Missing firmware

If the kernel reports a missing firmware file at boot, `surfd-hwprobe` lists it
and shows how to find the package:

```sh
dnf provides '/usr/lib/firmware/iwlwifi-*.ucode*'
```

## Mainline kernel

For hardware newer than Fedora's kernel (brand-new Wi-Fi, GPUs, laptops), the
Fedora kernel team's *kernel-vanilla* Copr repositories provide unmodified
upstream kernels:

```sh
sudo dnf copr enable @kernel-vanilla/stable      # latest stable series, or:
sudo dnf copr enable @kernel-vanilla/mainline    # latest -rc / mainline
sudo dnf --setopt=allow_vendor_change=1 upgrade \
  $(rpm -qa --qf '%{name} \n' 'kernel*' 'libperf*' perf python3-perf rtla rv | sort -u)
```

These kernels are **not signed for Secure Boot**: disable it or use
`sudo mokutil --disable-validation`. To go back:

```sh
dnf copr list | grep -Eo '@kernel-vanilla/[^ ]+ ' | xargs -r sudo dnf copr remove
sudo dnf --refresh --setopt=allow_vendor_change=1 distro-sync \
  $(rpm -qa 'kernel*' 'libperf*' perf python3-perf rtla rv --qf '%{name} \n' | sort -u)
# reboot into a kernel without "vanilla" in its name, then:
sudo dnf remove $(rpm -qa 'kernel' 'kernel*core*' 'kernel*modules*' 'kernel*devel*' | grep '.vanilla')
```

Details: <https://fedoraproject.org/wiki/Kernel_Vanilla_Repositories>.

## Known limitations

- **Intel IPU6/IPU7 MIPI cameras** (many 2021+ Intel laptops): limited open
  support; USB webcams work. RPM Fusion packages the vendor stack for some models.
- **Fingerprint readers**: only devices in libfprint's supported list
  (`sudo dnf install fprintd fprintd-pam`, then `fprintd-enroll`).
- **Very new Wi-Fi 7 / GPUs** may need the mainline kernel above, or a
  newer Fedora release.
- **Fractional scaling**: native Wayland apps are sharp; X11 apps running
  through Xwayland look soft at non-integer scales.
- **Screen sharing**: via xdg-desktop-portal-wlr. Sharing whole screens works
  in browsers and most apps; picking a single window is limited.
- **No window animations or rounded window corners** (Sway's design). The bar,
  notifications, launcher and GTK apps are rounded and animated.

## Arm

surfd builds an aarch64 (64-bit Arm) live ISO for **UEFI / Arm SystemReady** machines
(Ampere workstations, Snapdragon X laptops as Fedora support matures,
UEFI-booted boards, VMs on Arm Macs via UTM/Parallels).

- **Raspberry Pi 4/5**: not targeted by the ISO. Use Fedora's ARM images and
  `sudo dnf install surfd-default-config` on top, or boot the ISO with
  third-party UEFI firmware. A dedicated image is on the roadmap.
- **Apple Silicon**: not supported; use Fedora Asahi Remix.
- **Boards needing vendor kernels or U-Boot-only boot**: out of scope.

## Reporting hardware problems

Include `surfd-hwprobe --json`, `journalctl -b -k --no-pager | tail -200`,
and `~/.local/state/surfd/session.log`.
