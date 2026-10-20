#!/usr/bin/env bash
# headless-screenshot.sh — run the real surfd session (Sway, Waybar, mako,
# foot, fuzzel) on a headless Wayland output and capture screenshots.
#
# Used to check the look without a VM, and to produce docs/screenshots.
# Needs: sway waybar mako foot fuzzel grim dbus-run-session, plus rendered
# artwork (python3 theme/tools/render.py build/art).
#
#   tools/headless-screenshot.sh build/art docs/screenshots [theme variant mode]
set -Eeuo pipefail

ART="$(realpath "${1:?rendered artwork dir}")"
OUT="$(realpath -m "${2:?output dir}")"
THEME="${3:-tide}" VARIANT="${4:-dark}" MODE="${5:-tiling}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

for c in sway waybar mako foot grim dbus-run-session; do
    command -v "$c" >/dev/null || { echo "missing: $c" >&2; exit 1; }
done
mkdir -p "${OUT}"

work="$(mktemp -d)"
trap 'kill $(jobs -p) 2>/dev/null || true; rm -rf "${work}"' EXIT
mkdir -p "${work}"/{home,run,bin,sys/defaults}
chmod 700 "${work}/run"
cp "${REPO}/config/defaults/surfd.toml" "${work}/sys/defaults/"
ln -s "${ART}/themes" "${work}/sys/themes"
mkdir -p "${work}/sys/wallpapers/dynamic"
ln -s "${REPO}/wallpapers/third-party/dynamic/low-poly-mountain" "${work}/sys/wallpapers/dynamic/low-poly-mountain"
cat > "${work}/bin/surfctl" <<EOF
#!/bin/sh
PYTHONPATH="${REPO}/src/surfctl" exec python3 -m surfd "\$@"
EOF
chmod +x "${work}/bin/surfctl"

export HOME="${work}/home" XDG_RUNTIME_DIR="${work}/run" SURFD_SYSTEM_DIR="${work}/sys"
# Some apps (fuzzel) find home via passwd, not $HOME; XDG_* points them here.
export XDG_CONFIG_HOME="${HOME}/.config" XDG_STATE_HOME="${HOME}/.local/state" XDG_DATA_HOME="${HOME}/.local/share"
export SURFD_LIBEXEC="${REPO}/src/session/libexec" PATH="${work}/bin:${PATH}"
export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 LC_ALL=C.UTF-8
unset WAYLAND_DISPLAY SWAYSOCK DISPLAY

surfctl init -q
surfctl theme set "${THEME}" --variant "${VARIANT}" --no-reload >/dev/null
surfctl mode "${MODE}" --no-reload >/dev/null
surfctl generate -q

# A tiny stand-in for the welcome app and polkit agent in this test.
cat > "${work}/bin/lxpolkit" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "${work}/bin/lxpolkit"

# shellcheck disable=SC2016  # expanded by the inner shell on purpose
dbus-run-session -- bash -c '
  set -u
  sway --config "$HOME/.local/state/surfd/generated/sway/config" >"$0/sway.log" 2>&1 &
  for _ in $(seq 100); do ls "$XDG_RUNTIME_DIR"/sway-ipc.* >/dev/null 2>&1 && break; sleep 0.1; done
  export SWAYSOCK=$(ls "$XDG_RUNTIME_DIR"/sway-ipc.* | head -n1)
  export WAYLAND_DISPLAY=$(ls "$XDG_RUNTIME_DIR" | grep -E "^wayland-[0-9]+$" | head -n1)
  swaymsg -q output HEADLESS-1 resolution 1920x1080
  sleep 2
  swaymsg -q exec "foot -e sh -c \"echo \\\"\$ surfctl theme list\\\"; surfctl theme list; echo; echo \\\"\$ surfctl keys list | head\\\"; surfctl keys list | head -12; sleep 60\""
  swaymsg -q exec "foot -e sh -c \"surfctl explain layout; sleep 60\""
  sleep 2
  gdbus call --session --dest org.freedesktop.Notifications --object-path /org/freedesktop/Notifications \
    --method org.freedesktop.Notifications.Notify surfd 0 preferences-desktop "Welcome to surfd" \
    "Press Super + / for the key cheat sheet." "[]" "{}" 0 >/dev/null || true
  sleep 1.5
  grim "$1-desktop.png"
  if command -v fuzzel >/dev/null; then
    swaymsg -q exec "fuzzel 2>$0/fuzzel.log"
    sleep 1.5
    grim "$1-launcher.png"
  fi
  swaymsg -q exit
' "${work}" "${OUT}/${THEME}-${VARIANT}-${MODE}" || true

shopt -s nullglob
for f in "${OUT}/${THEME}-${VARIANT}-${MODE}"*.png; do echo "wrote $f"; done
[[ -s "${work}/fuzzel.log" ]] && grep -E "err|warn|loading configuration" "${work}/fuzzel.log" >&2
if [[ -f "${work}/sway.log" ]] && grep -E "\[ERROR\]" "${work}/sway.log" | grep -v -E "libinput|xwayland|Xwayland|backlight" >&2; then
    echo "(errors above are from sway's log)" >&2
fi
