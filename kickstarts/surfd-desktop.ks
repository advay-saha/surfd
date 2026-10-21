# surfd-desktop.ks — the Sway desktop, theming, apps and surfd components.
#
# No GNOME, no KDE. Every package here is either part of the session,
# part of the look, or a small everyday app. Anything else comes from
# Flathub or dnf after install.

%packages --exclude-weakdeps

# ---- surfd components (built from packaging/specs, served by build.sh) ----
surfd-release
surfd-logos
surfd-theme
surfd-wallpapers
plymouth-theme-surfd
surfd-default-config
surfctl
surfd-hwprobe
surfd-settings

# ---- compositor and session ----
sway
# sway hard-requires a "sway-config" provider. surfctl generates the real
# config, so take the minimal one and keep Fedora's opinionated one out.
sway-config-minimal
-sway-config-fedora
swaybg
swaylock
swayidle
waybar
fuzzel
mako
grim
slurp
wl-clipboard
brightnessctl
playerctl
libnotify
# capture, emoji typing, night light, drives, power, monitor, displays (surfd 0.2 features)
wf-recorder
swappy
wtype
wlsunset
udiskie
power-profiles-daemon
btop
wdisplays
gnome-keyring
xorg-x11-server-Xwayland
xdg-desktop-portal-wlr
xdg-desktop-portal-gtk
xdg-user-dirs
xdg-utils
polkit
lxpolkit

# ---- login screen ----
greetd
greetd-selinux
gtkgreet

# ---- audio ----
pipewire
pipewire-pulseaudio
pipewire-alsa
wireplumber
pavucontrol

# ---- look and feel ----
adw-gtk3-theme
papirus-icon-theme
breeze-cursor-theme
qt6ct
gsettings-desktop-schemas
dconf
rsms-inter-fonts
jetbrains-mono-fonts
google-noto-sans-fonts
google-noto-color-emoji-fonts

# ---- runtime for surfctl / Surf Settings ----
python3
python3-tomlkit
python3-gobject
gtk4
libadwaita

# ---- everyday apps (small, native; everything else via Flathub) ----
foot
firefox
thunar
gvfs
imv
mousepad
network-manager-applet
nm-connection-editor
blueman
system-config-printer

%end

%post --erroronfail
# greetd is the display manager. Enable it explicitly rather than relying
# on preset ordering inside the image transaction.
systemctl enable greetd.service
ln -sf /usr/lib/systemd/system/greetd.service /etc/systemd/system/display-manager.service

# Apply the surfd presets (shipped by surfd-release) to everything installed.
systemctl preset-all --preset-mode=enable-only

# Default Plymouth theme. livemedia-creator regenerates the live initramfs
# after %post, so no dracut run is needed here.
plymouth-set-default-theme surfd

# Sanity-check the shipped defaults and themes (non-fatal; logged to the
# build output so a broken theme pack is visible in CI logs).
/usr/bin/surfctl doctor --system || echo "surfd: surfctl doctor reported problems" >&2
%end
