#!/bin/sh
# showcase-term.sh — what the terminals show in `headless-screenshot.sh ... showcase`.
#   showcase-term.sh palette   the theme in use, its 16 terminal colours, the wallpaper
#   showcase-term.sh keys      the start of the key cheat sheet
set -u
bold() { printf '\033[1m%s\033[0m\n' "$*"; }
case "${1:-palette}" in
palette)
    bold "\$ surfctl theme info"
    surfctl theme info | head -n 1 | cut -c1-110
    printf '\n'
    for base in 40 100; do
        for i in 0 1 2 3 4 5 6 7; do printf '\033[%dm      ' $((base + i)); done
        printf '\033[0m\n'
    done
    printf '\n'
    bold "\$ surfctl wallpaper status"
    surfctl wallpaper status 2>&1 | head -n 1 | sed 's|/[^ ]*/||g' | cut -c1-110
    ;;
keys)
    bold "\$ surfctl keys list"
    surfctl keys list | head -n 14
    ;;
esac
exec sleep 60
