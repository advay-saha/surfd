#!/usr/bin/env bash
# check-packages.sh — confirm every package and group named in a flattened
# surfd kickstart exists for the target Fedora release and architecture.
#
# Catches renamed/retired packages before a 40-minute ISO build does.
# Needs a Fedora host with dnf5 and network access to the Fedora mirrors.
#
#   tools/check-packages.sh --releasever 44 --arch x86_64 \
#       --surfd-repo file:///path/to/out/repo build/surfd.ks
set -Eeuo pipefail

RELEASEVER=44
ARCH="$(uname -m)"
SURFD_REPO=""
KS=""

while (( $# )); do
    case "$1" in
        --releasever) RELEASEVER="${2:?}"; shift 2 ;;
        --arch)       ARCH="${2:?}"; shift 2 ;;
        --surfd-repo) SURFD_REPO="${2:?}"; shift 2 ;;
        -h|--help)    sed -n '2,10p' "$0"; exit 0 ;;
        *)            KS="$1"; shift ;;
    esac
done
[[ -f "${KS}" ]] || { echo "usage: $0 [--releasever N] [--arch A] [--surfd-repo URL] flattened.ks" >&2; exit 2; }
command -v dnf >/dev/null || { echo "dnf not found: run this on Fedora" >&2; exit 2; }

# Pull %packages bodies, strip comments/options, split into groups/packages.
mapfile -t entries < <(awk '/^%packages/{p=1;next} /^%end/{p=0} p' "${KS}" \
    | sed -e 's/#.*//' -e 's/[[:space:]]*$//' -e '/^$/d' | sort -u)

groups=() pkgs=() excluded=()
for e in "${entries[@]}"; do
    case "${e}" in
        -*) excluded+=("${e#-}") ;;
        @*) groups+=("${e#@}") ;;
        *)  pkgs+=("${e}") ;;
    esac
done

dnf_args=(--releasever="${RELEASEVER}" --forcearch="${ARCH}" --setopt=install_weak_deps=False
          --repo=fedora --repo=updates)
if [[ -n "${SURFD_REPO}" ]]; then
    dnf_args+=(--repofrompath="surfd,${SURFD_REPO}" --repo=surfd --setopt=surfd.gpgcheck=0)
fi

echo "Checking ${#pkgs[@]} packages and ${#groups[@]} groups for Fedora ${RELEASEVER}/${ARCH}..."
found="$(dnf repoquery "${dnf_args[@]}" --quiet --latest-limit=1 --qf '%{name}\n' "${pkgs[@]}" 2>/dev/null | sort -u)"

missing=0
for p in "${pkgs[@]}"; do
    if ! grep -qxF "${p}" <<<"${found}"; then
        # Some names are virtual provides; resolve those too.
        if ! dnf repoquery "${dnf_args[@]}" --quiet --whatprovides "${p}" 2>/dev/null | grep -q .; then
            echo "  MISSING package: ${p}"
            missing=$((missing + 1))
        fi
    fi
done
for g in "${groups[@]}"; do
    if ! dnf group info "${dnf_args[@]}" --quiet "${g}" >/dev/null 2>&1; then
        echo "  MISSING group:   @${g}"
        missing=$((missing + 1))
    fi
done
for x in "${excluded[@]}"; do
    dnf repoquery "${dnf_args[@]}" --quiet "${x}" 2>/dev/null | grep -q . \
        || echo "  note: excluded package '${x}' does not exist (exclusion is a no-op)"
done

if (( missing )); then
    echo "FAIL: ${missing} missing package(s)/group(s). Fix the kickstarts before building."
    exit 1
fi
echo "OK: all packages and groups resolve."
