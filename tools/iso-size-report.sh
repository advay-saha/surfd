#!/usr/bin/env bash
# iso-size-report.sh — show what takes space inside a surfd live ISO.
# Lists the 40 largest installed packages from the ISO's root filesystem.
# Needs root (loop mounts) on a Linux host with rpm installed.
#
#   sudo tools/iso-size-report.sh out/iso/surfd-0.2.0-f44-x86_64.iso
set -Eeuo pipefail

ISO="${1:?usage: $0 path/to/surfd.iso}"
[[ ${EUID} -eq 0 ]] || { echo "needs root for loop mounts" >&2; exit 1; }

work="$(mktemp -d)"
cleanup() {
    for m in "${work}/root" "${work}/sq" "${work}/iso"; do
        mountpoint -q "${m}" && umount "${m}"
    done
    rm -rf "${work}"
}
trap cleanup EXIT
mkdir -p "${work}"/{iso,sq,root}

mount -o loop,ro "${ISO}" "${work}/iso"
mount -o loop,ro "${work}/iso/LiveOS/squashfs.img" "${work}/sq"
# Fedora live squashfs holds either the root tree directly or an ext4 image.
if [[ -f "${work}/sq/LiveOS/rootfs.img" ]]; then
    mount -o loop,ro "${work}/sq/LiveOS/rootfs.img" "${work}/root"
    root="${work}/root"
else
    root="${work}/sq"
fi

printf 'ISO size:       %s\n' "$(du -h "${ISO}" | cut -f1)"
printf 'squashfs size:  %s\n' "$(du -h "${work}/iso/LiveOS/squashfs.img" | cut -f1)"
printf 'packages:       %s\n\n' "$(rpm --root "${root}" -qa | wc -l)"
echo "Largest packages (installed size):"
rpm --root "${root}" -qa --qf '%{SIZE}\t%{NAME}\n' | sort -rn | head -40 \
    | awk -F'\t' '{ printf "  %8.1f MiB  %s\n", $1/1048576, $2 }'
