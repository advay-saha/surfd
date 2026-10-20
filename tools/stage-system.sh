#!/usr/bin/env bash
# stage-system.sh — lay out a fake /usr/share/surfd the way the packages install it,
# from the repository and rendered artwork, for the screenshot and test scripts.
#
#   tools/stage-system.sh build/art DIR
#
# DIR gets defaults/, themes/ (surfd's own + one per wallpaper) and wallpapers/
# (surfd/<colourway>, dynamic/<set>, static/). Files are symlinks into the repository.
set -Eeuo pipefail

ART="$(realpath "${1:?rendered artwork dir}")"
SYS="${2:?target dir}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "${SYS}"/{defaults,themes,wallpapers/dynamic,wallpapers/surfd}
cp "${REPO}/config/defaults/surfd.toml" "${SYS}/defaults/"
ln -s "${ART}"/themes/* "${REPO}"/wallpapers/third-party/themes/* "${SYS}/themes/"
ln -s "${REPO}"/wallpapers/third-party/dynamic/* "${SYS}/wallpapers/dynamic/"
ln -s "${REPO}/wallpapers/third-party/static" "${SYS}/wallpapers/static"
# real folders (not links) so the gallery, which does not follow folder links, finds the colourways
for c in tide driftwood kelp dusk; do cp -rs "${REPO}/wallpapers/generated/$c" "${SYS}/wallpapers/surfd/"; done
