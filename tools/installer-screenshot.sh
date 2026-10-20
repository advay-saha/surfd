#!/usr/bin/env bash
# installer-screenshot.sh — walk through Surf Installer in demo mode (no disk is
# touched) inside a headless surfd session, checking each screen and saving
# screenshots.
#
#   tools/installer-screenshot.sh build/art OUTDIR [python]
set -Eeuo pipefail

ART="$(realpath "${1:?rendered artwork dir}")"
OUT="$(realpath -m "${2:?output dir}")"
PY="${3:-python3}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "${OUT}"

work="$(mktemp -d)"
trap 'kill $(jobs -p) 2>/dev/null || true; rm -rf "${work}"' EXIT
mkdir -p "${work}"/{home,run,bin,share/icons/hicolor/scalable/apps}
chmod 700 "${work}/run"
"${REPO}/tools/stage-system.sh" "${ART}" "${work}/sys"   # every theme and wallpaper, as the packages install them
cp "${REPO}/src/installer/data/org.surfd.Installer.svg" "${work}/share/icons/hicolor/scalable/apps/"
cat > "${work}/bin/surfctl" <<EOS
#!/bin/sh
PYTHONPATH="${REPO}/src/surfctl" exec ${PY} -m surfd "\$@"
EOS
printf '#!/bin/sh\nexit 0\n' > "${work}/bin/lxpolkit"
chmod +x "${work}/bin/"*

export HOME="${work}/home" XDG_RUNTIME_DIR="${work}/run" SURFD_SYSTEM_DIR="${work}/sys"
export XDG_CONFIG_HOME="${HOME}/.config" XDG_STATE_HOME="${HOME}/.local/state" XDG_DATA_HOME="${HOME}/.local/share"
export XDG_DATA_DIRS="${work}/share:/usr/local/share:/usr/share"
export SURFD_LIBEXEC="${REPO}/src/session/libexec" PATH="${work}/bin:${PATH}"
export PYTHONPATH="${REPO}/src/installer:${REPO}/src/surfctl:${REPO}/src/settings"
export SURF_INSTALLER_DRY_RUN=1 SURF_INSTALLER_FAKE_DISKS="${REPO}/src/installer/tests/fake-disks.json"
export SURF_INSTALLER_PACE=0.3
export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 LC_ALL=C.UTF-8
export GSK_RENDERER=cairo GDK_BACKEND=wayland
unset WAYLAND_DISPLAY SWAYSOCK DISPLAY

surfctl init -q
surfctl wallpaper sync theme --no-reload >/dev/null   # the same frame whatever the time: night, for the dark style
surfctl generate -q
touch "${HOME}/.config/surfd/.welcome-done"

# shellcheck disable=SC2016  # expanded by the inner shell on purpose
dbus-run-session -- bash -c '
  set -u
  sway --config "$HOME/.local/state/surfd/generated/sway/config" >"$1/sway.log" 2>&1 &
  for _ in $(seq 100); do ls "$XDG_RUNTIME_DIR"/sway-ipc.* >/dev/null 2>&1 && break; sleep 0.1; done
  export SWAYSOCK=$(ls "$XDG_RUNTIME_DIR"/sway-ipc.* | head -n1)
  export WAYLAND_DISPLAY=$(ls "$XDG_RUNTIME_DIR" | grep -E "^wayland-[0-9]+$" | head -n1)
  swaymsg -q output HEADLESS-1 resolution 1600x1000
  swaymsg -q "for_window [app_id=org.surfd.Installer] floating enable"
  sleep 2
  "$3" "$0" "$2" 2>"$1/app.log" | tee "$1/walk.log"
  swaymsg -q exit
' "${REPO}/src/installer/tests/gui_walkthrough.py" "${work}" "${OUT}" "${PY}" || true

grep -iE "traceback|error|critical" -A4 "${work}/app.log" | grep -vE "a11y|accessibility" | head -30 || true
ls -1 "${OUT}"/installer-*.png 2>/dev/null
grep -q '^OK:' "${work}/walk.log" || { echo "installer walkthrough FAILED" >&2; exit 1; }
