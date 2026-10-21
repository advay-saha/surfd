# What surfd does

Everything below is in surfd 0.2. Keys use the default bindings (change them in
`~/.config/surfd/surfd.toml`, Surf Settings → Keyboard, or `surfctl keys`); **Super + /**
lists every key, and **Super + Alt + Space** opens the surfd menu, which reaches almost
everything here without remembering a key.

Most of this list came from comparing surfd with Omarchy, Manjaro Sway, CachyOS's
Hyprland and niri editions and Regolith: what they have that a Sway desktop usually lacks.

## Flyouts and notifications

| # | Feature | How |
|---|---|---|
| 1 | Volume flyout: a bar, the level and the output device | volume keys; scroll on the bar's volume |
| 2 | Mute shows in the flyout (muted level greyed out) | mute key; right-click the bar's volume |
| 3 | Microphone mute and level flyout | mic-mute key; the bar's `mic` module |
| 4 | Brightness flyout; brightness never drops to black (stops at 1 %) | brightness keys; scroll on `backlight` |
| 5 | Keyboard backlight keys with a flyout | keyboard backlight keys |
| 6 | Caps Lock flyout (on / off) | Caps Lock |
| 7 | Num Lock flyout | Num Lock |
| 8 | Next keyboard layout, with a flyout naming it | **Super + Alt + K** |
| 9 | Media keys show what is playing (▶ artist — title); stop key works | media keys |
| 10 | Flyouts can be turned off, moved, and their step changed | `[osd]`; Surf Settings → Bar → Flyouts |
| 11 | Flyouts replace each other instead of stacking up | — |
| 12 | Do not disturb: notifications wait until you switch it off; urgent ones and flyouts still show | **Super + Ctrl + D**; `surfctl dnd` |
| 13 | Bar module for notifications (click: do not disturb, right-click: history, middle: dismiss all) | `notifications` module |
| 14 | Notification history; pick one to see it again | **Super + Alt + N**; `surfctl notifications` |
| 15 | Low battery warning (default 20 %) | `[power] battery_warning` |
| 16 | Critical battery warning that stays until dismissed (default 8 %) | `[power] battery_critical` |
| 17 | Flyout when the charger is plugged in or out | — |

## The surfd menu and pickers

| # | Feature | How |
|---|---|---|
| 18 | The surfd menu: apps, capture, toggles, theme, wallpaper, clipboard, emoji, calculator, notifications, windows, connections, setup, update, system | **Super + Alt + Space**; right-click ⏻ |
| 19 | Capture menu: every screenshot and recording, colour picker, screenshots folder | menu → capture |
| 20 | Toggles menu: do not disturb, night light, keep awake, dark/light, tiling/floating, bar | menu → toggles |
| 21 | Connections menu: Wi-Fi, Bluetooth, sound output, power profile | menu → connections |
| 22 | Setup menu: Surf Settings, keyboard shortcuts, displays (wdisplays), printers, edit surfd.toml, health check | menu → setup |
| 23 | System menu: lock, log out, suspend, restart, shut down, reload the desktop | menu → system |
| 24 | Install updates from the menu (dnf, then Flatpak) | menu → update; `surfctl update` |
| 25 | Theme picker | **Super + Shift + T**; `surfctl menu theme` |
| 26 | Dark / light style toggle | **Super + Shift + D** |
| 27 | Next / previous wallpaper from the gallery | **Super + Ctrl + Space**; `surfctl wallpaper next` |
| 28 | Window switcher across workspaces and the scratchpad, with app icons | **Alt + Tab**; `surfctl windows` |
| 29 | Clipboard history (text; password managers' copies are skipped; private file) | **Super + V** |
| 30 | Clear the clipboard history | Super + V → clear history |
| 31 | Emoji picker: searchable by name, copies and types the emoji | **Super + .** |
| 32 | Calculator: type a sum, the result is copied; keep calculating from the result | **Super + Ctrl + C**, Calculator key; `surfctl calc 2^10/3` |
| 33 | Sound output and input picker | **Super + Alt + A**, **Super + Mute**, click the bar's volume |
| 34 | Bluetooth menu: connect or disconnect paired devices, power, pair new | **Super + Alt + B**; click the bar's Bluetooth |
| 35 | Wi-Fi menu on a key | **Super + Alt + W** |
| 36 | Power profile: cycle saver / balanced / performance, or pick | **Super + Alt + P**; click the battery |

## Screenshots, recording, colour

| # | Feature | How |
|---|---|---|
| 37 | Screenshot of the focused window (with its title bar) | **Ctrl + Print**, **Super + Shift + W** |
| 38 | Screenshot of the current display (multi-monitor aware) | menu → capture |
| 39 | Screenshot an area and annotate it (swappy) | **Super + Ctrl + Shift + S** |
| 40 | Delayed screenshot with a countdown | menu; `surfctl screenshot output --delay 5` |
| 41 | The saved-screenshot notification shows a thumbnail; click opens it, buttons annotate or show the folder | — |
| 42 | Choose the screenshots folder | `[capture] screenshots` |
| 43 | Two screenshots in the same second never overwrite each other | — |
| 44 | Record an area of the screen (press again to stop) | **Alt + Print**, **Super + Shift + R** |
| 45 | Record the whole display | **Ctrl + Alt + Print** |
| 46 | Record the computer's sound with it | `[capture] record_audio` |
| 47 | Recording indicator in the bar with a timer; click to stop | `recording` module (on by default) |
| 48 | Colour picker: click a pixel, its hex code is copied and shown | **Super + Print**, **Super + Shift + X** |

## Windows and workspaces

| # | Feature | How |
|---|---|---|
| 49 | Automatic tiling: new windows split along the longer side (a spiral, like Hyprland's dwindle) | `layout.autotile` (on) |
| 50 | Drop-down terminal (show / hide, keeps running) | **Super + Shift + Return** |
| 51 | System monitor (btop) in a floating window | **Ctrl + Shift + Esc** |
| 52 | Pin a floating window to every workspace | **Super + P** |
| 53 | Make a window see-through and back | **Super + O** |
| 54 | Centre a floating window | **Super + Alt + C** |
| 55 | Resize without entering resize mode | **Super + Alt + arrows** |
| 56 | Close every window on the workspace | **Super + Ctrl + Q** |
| 57 | Jump to the first empty workspace | **Super + X** |
| 58 | Move the workspace to the display on the left / right | **Super + Ctrl + Shift + ← / →** |
| 59 | Focus the next display | **Super + Ctrl + Tab** |
| 60 | Workspace back-and-forth: pressing the current workspace's key goes back | `layout.workspace_back_and_forth` |
| 61 | Smart gaps: no gaps around a lone window | `layout.smart_gaps` |
| 62 | Smart borders: no border around a lone window | `layout.smart_borders` (on) |
| 63 | Windows that ask for attention get it without stealing focus mid-typing | — |
| 64 | File dialogs, Firefox's Library, Steam's friends list, print and portal dialogs float | — |

## Bar

| # | Feature | How |
|---|---|---|
| 65 | Recording module (hidden when not recording) | `recording` |
| 66 | Updates module (hidden when up to date; click installs) | `updates` |
| 67 | Power profile module | `profile` |
| 68 | Night light module | `nightlight` |
| 69 | Microphone module | `mic` |
| 70 | Free disk space module | `disk` |
| 71 | Clipboard history button | `clipboard` |
| 72 | Clock: click for the full date with seconds; calendar with week numbers, scroll for months | `clock` |
| 73 | Volume: click for the sound menu, right-click mutes, middle-click opens the mixer, scroll with a flyout | `audio` |
| 74 | Brightness: scroll with a flyout | `backlight` |
| 75 | Battery: shows when plugged in; click picks a power profile | `battery` |
| 76 | Bluetooth: click opens the Bluetooth menu | `bluetooth` |
| 77 | Hide / show the bar | **Super + Shift + B** |
| 78 | The `full` preset shows all of the above | `surfctl bar preset full` |

## Display, power, input

| # | Feature | How |
|---|---|---|
| 79 | Night light: off, sunset to sunrise, or always; warmth adjustable | **Super + Ctrl + N**; `[display] night_light` |
| 80 | Clamshell mode: lid closed with an external display switches the built-in screen off | `display.clamshell` (on) |
| 81 | Adaptive sync (FreeSync / G-Sync compatible) | `display.adaptive_sync` |
| 82 | Keep awake: no lock, screen-off or sleep until switched off | **Super + Ctrl + I**; `surfctl awake` |
| 83 | Key repeat delay and rate | `input.repeat_delay`, `input.repeat_rate` |
| 84 | Num Lock on at login | `input.numlock` (on) |
| 85 | Pointer hides while you type | `input.hide_cursor_typing` (on) |
| 86 | Pointer hides after it has been still for a while | `input.hide_cursor_after` |
| 87 | Natural scrolling for mice too | `input.mouse_natural_scroll` |
| 88 | Scroll speed | `input.scroll_factor` |
| 89 | Tap and drag on touchpads | — |

## System

| # | Feature | How |
|---|---|---|
| 90 | USB drives mount automatically, with a notification and a tray menu (udiskie) | — |
| 91 | Screen sharing asks which display to share (in a fuzzel menu) | — |
| 92 | Screenshots and screen sharing in apps go through the right portal | — |
| 93 | A keyring for apps that store passwords (browsers, editors, mail) | gnome-keyring |
| 94 | Updates are checked a few minutes after login and every 6 hours (system and Flatpak) | `[updates] check` |
| 95 | Background helpers stop at logout and restart cleanly on reload | — |

## Look

| # | Feature | How |
|---|---|---|
| 96 | Surf Settings, Welcome and the installer use the surfd look: the theme's colours, monospace titles, labels and buttons, small corners, thin borders | follows your theme |
| 97 | Settings sections read like the menus: "› theme", "› windows" | — |
| 98 | Menus use the monospace font, so their columns line up | — |
| 99 | Every new option is in Surf Settings | Look, Windows, Bar, Keyboard, Apps pages |
| 100 | Every feature has a `surfctl` command, for scripts and your own key bindings | `surfctl --help` |

## Not yet

Things the compared setups have that surfd does not: an overview of all windows
(niri, GNOME), animated workspace switching (Hyprland), fingerprint login and web-app
launchers (Omarchy), and a GUI for arranging displays inside Surf Settings (wdisplays
is in the menu instead).
