#!/usr/bin/env bash
# ci-log-tail.sh — after a failed CI step, show the end of its log as an error
# annotation on the run page (readable without downloading the full log).
#
#   tools/ci-log-tail.sh build.log [lines]
set -uo pipefail

log="${1:?log file}"
lines="${2:-80}"
[[ -s "${log}" ]] || { echo "::error title=Build failed::no log at ${log}"; exit 0; }
# Lines with "error", "FAILED" or a traceback first, then the end of the log.
{
    echo "--- error lines ---"
    grep -nE "error:|Error:|ERROR|FAILED|Traceback|No match for|nothing provides|Bad exit status" "${log}" | tail -n 25
    echo "--- last ${lines} lines ---"
    tail -n "${lines}" "${log}"
} | cut -c1-300 > "${log}.tail"
# Workflow commands need %, CR and LF escaped to keep the message on one line.
msg="$(sed -e 's/%/%25/g' -e 's/\r/%0D/g' "${log}.tail" | awk 'BEGIN{ORS="%0A"} {print}')"
echo "::error title=Build failed (end of ${log})::${msg}"
{
    echo "### Build failed: end of \`${log}\`"
    echo '```'
    cat "${log}.tail"
    echo '```'
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
