# surfd-base.ks — the operating system underneath the desktop.
#
# Everything here is what makes surfd "a normal Fedora": dnf, systemd,
# SELinux enforcing, NetworkManager, firewalld, Fedora's kernel and the
# broad firmware set. Nothing desktop-specific lives in this file.

lang en_US.UTF-8
keyboard us
timezone Etc/UTC --utc
selinux --enforcing
firewall --enabled --service=mdns
network --bootproto=dhcp --device=link --activate
rootpw --lock
services --enabled=NetworkManager,firewalld,chronyd,systemd-resolved,bluetooth,cups.socket,power-profiles-daemon,fwupd-refresh.timer --disabled=sshd

# install_weak_deps=False for the image build. The installed system keeps
# the same policy via /etc/dnf/libdnf5.conf.d/20-surfd.conf (reversible,
# see docs/customization.md#weak-dependencies).
%packages --exclude-weakdeps

@core

# Kernel: Fedora's current stable kernel. The optional mainline kernel
# (kernel-vanilla Copr) is documented in docs/hardware.md.
kernel
kernel-modules
kernel-modules-extra

# Firmware: the full linux-firmware split plus Fedora's hardware-support
# group (Wi-Fi, Bluetooth, GPU, audio DSP firmware).
@hardware-support
linux-firmware
alsa-sof-firmware
alsa-ucm
alsa-utils

# Graphics: Mesa provides every open Wayland-capable GPU driver
# (Intel, AMD, nouveau, virtio, Arm Mali/Adreno via panfrost/freedreno).
mesa-dri-drivers
mesa-vulkan-drivers
mesa-va-drivers
mesa-libEGL
mesa-libgbm

# System. The message bus and logind's PAM module are named explicitly: with
# --exclude-weakdeps they are not guaranteed, and without them there is no
# login session (no XDG_RUNTIME_DIR, so Sway and the login screen cannot start).
dbus
dbus-broker
dbus-common
systemd-pam
polkit
plymouth
plymouth-plugin-two-step
selinux-policy-targeted
policycoreutils
firewalld
chrony
systemd-resolved
zram-generator-defaults
fwupd
power-profiles-daemon
upower
NetworkManager
NetworkManager-wifi
NetworkManager-bluetooth
NetworkManager-tui
wpa_supplicant
bluez
cups
cups-filters
ipp-usb
flatpak
sudo
dnf5-plugins
bash-completion
man-db
man-pages
nano
vim-minimal
tar
unzip
pciutils
usbutils
glibc-langpack-en

# Fedora branding is replaced, per the Fedora Remix guidelines.
-fedora-logos
-fedora-release
-fedora-release-common
-fedora-release-identity-basic
generic-logos

%end

%post --erroronfail
# Default to the graphical session (greetd is enabled by its preset).
systemctl set-default graphical.target

# The system bus must run, or logind cannot start sessions. Enable it
# explicitly and stop the build if anything a login session needs is missing.
systemctl enable dbus-broker.service
for f in /usr/bin/dbus-broker /usr/lib/systemd/system/dbus.socket /usr/lib/systemd/systemd-logind; do
    [ -e "$f" ] || { echo "surfd: missing $f, the image would have no login sessions" >&2; exit 1; }
done
ls /usr/lib*/security/pam_systemd.so >/dev/null || { echo "surfd: pam_systemd.so missing" >&2; exit 1; }

# Keep image builds reproducible: no background metadata churn in the image.
systemctl disable dnf-makecache.timer 2>/dev/null || :

# Flathub as a system remote. The build host has network access; the
# surfd-flathub.service unit retries on first boot if this step was offline.
flatpak remote-add --system --if-not-exists flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo || \
    echo "surfd: Flathub not added at build time; first-boot unit will retry"
%end
