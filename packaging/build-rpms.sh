#!/usr/bin/env bash
# build-rpms.sh — build every surfd RPM from this checkout.
#
#   packaging/build-rpms.sh [--out DIR] [--srpm-only] [--spec NAME] [-- rpmbuild args]
#
# Creates surfd-<version>.tar.gz from the working tree (tracked and new,
# non-ignored files) and runs rpmbuild for each spec in packaging/specs.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(cat "${ROOT}/VERSION")"
OUT="${ROOT}/out/repo"
SRPM_ONLY=0
ONLY=""
EXTRA=()

while (( $# )); do
    case "$1" in
        --out) OUT="$(realpath -m "$2")"; shift 2 ;;
        --srpm-only) SRPM_ONLY=1; shift ;;
        --spec) ONLY="$2"; shift 2 ;;
        --) shift; EXTRA=("$@"); break ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

top="$(mktemp -d)"
trap 'rm -rf "${top}"' EXIT
mkdir -p "${top}"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "${OUT}"

# Source tarball from the working tree.
(
    cd "${ROOT}"
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        git ls-files -z --cached --others --exclude-standard
    else
        find . -path ./out -prune -o -path ./build -prune -o -path ./.git -prune -o -type f -print0 | sed -z 's|^\./||'
    fi
) | sort -z > "${top}/files.lst"
mtime="${SOURCE_DATE_EPOCH:-$(git -C "${ROOT}" log -1 --format=%ct 2>/dev/null || date +%s)}"
tar -C "${ROOT}" --null --transform "s|^|surfd-${VERSION}/|" --owner=0 --group=0 --mtime="@${mtime}" \
    -czf "${top}/SOURCES/surfd-${VERSION}.tar.gz" -T "${top}/files.lst"

mode=(-ba)
(( SRPM_ONLY )) && mode=(-bs)

for spec in "${ROOT}"/packaging/specs/*.spec; do
    name="$(basename "${spec}" .spec)"
    [[ -n "${ONLY}" && "${ONLY}" != "${name}" ]] && continue
    echo "==> ${name}"
    rpmbuild "${mode[@]}" --define "_topdir ${top}" "${EXTRA[@]}" "${spec}"
done

find "${top}/RPMS" "${top}/SRPMS" -name '*.rpm' -exec cp {} "${OUT}/" \;
echo "RPMs in ${OUT}:"
ls -1 "${OUT}"
