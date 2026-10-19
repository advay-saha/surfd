#!/usr/bin/env bash
# measure-ram.sh — measure idle memory of a running surfd session.
#
# Run inside the logged-in Sway session after it has been idle for ~2
# minutes (no browser open). The project target is < 400 MB used.
# "Used" here is MemTotal - MemAvailable, the same figure `free` reports.
set -euo pipefail

settle="${1:-0}"
if (( settle > 0 )); then
    echo "Waiting ${settle}s for the session to settle..."
    sleep "${settle}"
fi

read -r total avail < <(awk '/^MemTotal:/{t=$2} /^MemAvailable:/{a=$2} END{print t, a}' /proc/meminfo)
used_mb=$(( (total - avail) / 1024 ))

printf 'Used memory: %d MiB (target: < 400 MiB) — %s\n' "${used_mb}" \
    "$( (( used_mb < 400 )) && echo PASS || echo OVER)"
printf 'Kernel: %s   Session: %s\n\n' "$(uname -r)" "${XDG_CURRENT_DESKTOP:-unknown}"
echo "Top processes by resident memory:"
ps -eo rss=,comm= --sort=-rss | head -15 | awk '{ printf "  %7.1f MiB  %s\n", $1/1024, $2 }'
if [[ -r /sys/block/zram0/mm_stat ]]; then
    echo
    echo "zram swap in use: $(( $(awk '{print $1}' /sys/block/zram0/mm_stat) / 1048576 )) MiB (uncompressed)"
fi
