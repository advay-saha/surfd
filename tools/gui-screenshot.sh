#!/usr/bin/env bash
# gui-screenshot.sh — open Surf Settings (each page) and the Welcome app in a
# headless surfd session and capture screenshots. Smoke test + docs images.
#
#   tools/gui-screenshot.sh build/art docs/screenshots [python] [theme] [variant]
#
# Needs: sway grim dbus-run-session, Python with GObject + GTK 4 + libadwaita.
set -Eeuo pipefail

ART="$(realpath "${1:?rendered artwork dir}")"
OUT="$(realpath -m "${2:?output dir}")"
PY="${3:-python3}" THEME="${4:-tide}" VARIANT="${5:-dark}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "${OUT}"

work="$(mktemp -d)"
trap 'kill $(jobs -p) 2>/dev/null || true; rm -rf "${work}"' EXIT
mkdir -p "${work}"/{home,run,bin,sys/defaults}
chmod 700 "${work}/run"
cp "${REPO}/config/defaults/surfd.toml" "${work}/sys/defaults/"
ln -s "${ART}/themes" "${work}/sys/themes"
cat > "${work}/bin/surfctl" <<EOF
#!/bin/sh
PYTHONPATH="${REPO}/src/surfctl" exec ${PY} -m surfd "\$@"
EOF
printf '#!/bin/sh\nexit 0\n' > "${work}/bin/lxpolkit"
chmod +x "${work}/bin/"*

export HOME="${work}/home" XDG_RUNTIME_DIR="${work}/run" SURFD_SYSTEM_DIR="${work}/sys"
export XDG_CONFIG_HOME="${HOME}/.config" XDG_STATE_HOME="${HOME}/.local/state" XDG_DATA_HOME="${HOME}/.local/share"
export SURFD_LIBEXEC="${REPO}/src/session/libexec" PATH="${work}/bin:${PATH}"
export PYTHONPATH="${REPO}/src/surfctl:${REPO}/src/settings"
export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 LC_ALL=C.UTF-8
export GSK_RENDERER=cairo GDK_BACKEND=wayland
unset WAYLAND_DISPLAY SWAYSOCK DISPLAY

surfctl init -q
surfctl theme set "${THEME}" --variant "${VARIANT}" --no-reload >/dev/null
surfctl generate -q
touch "${HOME}/.config/surfd/.welcome-done"   # we launch the Welcome app explicitly

# shellcheck disable=SC2016  # expanded by the inner shell on purpose
dbus-run-session -- bash -c '
  set -u
  work=$1 out=$2 py=$3 tag=$4 tag_theme=$5 tag_variant=$6
  sway --config "$HOME/.local/state/surfd/generated/sway/config" >"$work/sway.log" 2>&1 &
  for _ in $(seq 100); do ls "$XDG_RUNTIME_DIR"/sway-ipc.* >/dev/null 2>&1 && break; sleep 0.1; done
  export SWAYSOCK=$(ls "$XDG_RUNTIME_DIR"/sway-ipc.* | head -n1)
  export WAYLAND_DISPLAY=$(ls "$XDG_RUNTIME_DIR" | grep -E "^wayland-[0-9]+$" | head -n1)
  swaymsg -q output HEADLESS-1 resolution 1600x1000
  sleep 2
  for page in appearance layout bar input apps system; do
    "$py" -m surf_settings.app "$page" >>"$work/app.log" 2>&1 &
    pid=$!
    sleep 3
    grim "$out/settings-$tag-$page.png"
    kill $pid; wait $pid 2>/dev/null
  done
  echo "--- functional GUI test ---"
  "$py" "$0" "$out" 2>>"$work/app.log" | tee "$work/smoke.log"
  # the functional test above leaves another theme and accent behind: start the tour from the default look
  surfctl reset --yes --no-reload >/dev/null 2>&1 || true
  surfctl theme set "$tag_theme" --variant "$tag_variant" >/dev/null 2>&1 || true
  sleep 3
  "$py" -m surf_settings.welcome >>"$work/app.log" 2>&1 &
  pid=$!
  sleep 3
  grim "$out/welcome-$tag-1.png"
  swaymsg -q "[app_id=org.surfd.Welcome] focus"
  # advance one page with the keyboard (Tab to Next, Enter)
  kill $pid; wait $pid 2>/dev/null
  swaymsg -q exit
' "${REPO}/src/settings/tests/gui_smoke.py" "${work}" "${OUT}" "${PY}" "${THEME}-${VARIANT}" "${THEME}" "${VARIANT}" || true

echo "--- application log (warnings/errors) ---"
grep -iE "error|critical|warning|traceback" -A3 "${work}/app.log" | grep -v "Theme parser error" | head -40 || true
ls -1 "${OUT}/settings-${THEME}-${VARIANT}-"*.png "${OUT}/welcome-${THEME}-${VARIANT}-"*.png 2>/dev/null
if ! grep -q '^OK:' "${work}/smoke.log" 2>/dev/null; then
    echo "functional GUI test FAILED" >&2
    exit 1
fi
