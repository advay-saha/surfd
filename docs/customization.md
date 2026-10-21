# Customizing surfd

Everything about the desktop lives in one plain-text file:

```
~/.config/surfd/surfd.toml
```

It is created from `/usr/share/surfd/defaults/surfd.toml` on your first login,
with your installer keyboard layout filled in. You only need the keys you
change; anything missing falls back to the defaults, so upgrades can add new
settings without touching your file.

There are three equivalent ways to change it, and all three keep your comments:

| Way | Example | Applies |
|---|---|---|
| `surfctl` | `surfctl accent '#88c0d0'` | immediately |
| Surf Settings (**Super + ,**) | pick a colour swatch | immediately |
| A text editor | change `accent = "#88c0d0"` | after `surfctl reload` (or **Super + Shift + C**) |

Every key with its default and accepted values is listed in
[settings-reference.md](settings-reference.md); `surfctl explain` prints the
same thing with your current values.

## surfctl cheat sheet

```sh
# look
surfctl theme list
surfctl theme set kelp                      # switch theme pack (and to its wallpaper)
surfctl theme set red-cave --keep-wallpaper # only the colours
surfctl theme set tide --variant light
surfctl theme variant toggle                # dark <-> light
surfctl accent '#e88bc4'                    # accent colour
surfctl accent reset                        # back to the theme's accent
surfctl wallpaper set ~/Pictures/pier.jpg --mode fill
surfctl wallpaper dynamic desert-sands      # a wallpaper that changes through the day
surfctl wallpaper sync theme                # ...or follows light/dark; "auto" = time of day
surfctl wallpaper reset                     # back to the default wallpaper
surfctl font ui "Inter" 11
surfctl font mono "JetBrains Mono" 12
surfctl radius 14                           # bar, notifications, launcher, login screen
surfctl gaps 10 6                           # inner, outer

# windows and bar
surfctl mode floating                       # mouse-friendly: windows float with title bars
surfctl mode tiling
surfctl bar position bottom
surfctl bar style docked                    # or floating (detached, rounded)
surfctl bar preset classic                  # default | minimal | classic | full
surfctl bar layout left=workspaces,mode center=clock right=tray,network,audio,battery,power
surfctl bar modules                         # what you can put in the bar

# keys and apps
surfctl keys list
surfctl keys actions
surfctl keys bind Mod+F1 exec foot -e htop
surfctl keys bind Mod+Shift+Return terminal
surfctl keys unbind Mod+z
surfctl apps set browser flatpak run org.mozilla.firefox
surfctl apps set terminal foot

# anything else
surfctl set input.natural_scroll false
surfctl set idle.lock_after 600
surfctl get theme.accent
surfctl explain bar

# safety net
surfctl doctor                              # check config, themes and programs
surfctl reset                               # everything back to defaults (backup kept)
surfctl reset bar                           # just one section
surfctl backups list
surfctl backups restore latest
```

Each command validates first. If something is wrong you get a clear message
and **nothing is written**, for example:

```
$ surfctl accent blue
error: theme.accent: 'blue' is not a colour; use '#rgb' or '#rrggbb'
(no changes were made)
```

## Reset to defaults

```sh
surfctl reset            # asks first; a timestamped backup is saved
surfctl reset --yes      # no question (scripts)
surfctl reset keys       # only the [keys] section
surfctl backups restore latest
```

Backups are in `~/.local/state/surfd/backups/`. Surf Settings has the same
buttons under **System**.

If your file is so broken that the desktop cannot start from it, surfd still
logs you in: it uses the last configuration that worked (or a minimal
built-in one) and shows a bar explaining how to fix it.

## Key bindings

```toml
[keys]
modifier = "Super"          # what "Mod" means; "Alt" is the other choice

[keys.bindings]
"Mod+Return" = "terminal"
"Mod+Shift+3" = "move-to-workspace 3"
"Mod+F1" = "exec foot -e htop"
"Mod+t" = "sway layout toggle tabbed split"   # any raw Sway command
"Mod+z" = "none"                              # disable a default
```

**Super + /** opens every binding in a searchable list; pick one to run it.
Media, volume and brightness keys work on the lock screen too.

`exec` commands cannot contain `;` or `,` (Sway would split them into
separate commands). Put longer commands in a script and bind
`exec ~/bin/my-script`.

## Mouse-friendly mode and touchpad

`surfctl mode floating` makes every window float with a title bar, like a
traditional desktop: drag by the title bar, or hold **Super** and drag
anywhere (left button moves, right button resizes). The `classic` bar preset
adds a task list. Tiling and floating can be mixed at any time with
**Super + Shift + Space**.

Touchpad gestures (`input.gestures`): three-finger swipe left/right switches
workspace, swipe up opens the launcher, four-finger swipe up toggles fullscreen.

## Taking over one app by hand

surfctl writes some files where apps expect them: `~/.config/foot/foot.ini`,
`fuzzel/fuzzel.ini`, `mako/config`, `swaylock/config`, `gtk-3.0/*`,
`gtk-4.0/*`, `qt6ct/qt6ct.conf`. Each starts with a line saying
*"Managed by surfctl"*. **Delete that line** and surfctl will never touch that
file again: you own it. `surfctl doctor` lists the files you have taken over.

Sway and Waybar configs are generated into `~/.local/state/surfd/generated/`
and are always overwritten. To add raw Sway configuration, drop `*.conf` files
into `~/.config/surfd/sway.d/`; they are included last, so they can override
anything.

## Keeping your setup in git

```sh
cd ~/.config/surfd
git init && git add surfd.toml sway.d && git commit -m "my desktop"
```

Themes you made live in `~/.local/share/surfd/themes/`; add them too.

## Wallpapers

By default surfd shows **Low-poly mountain**, a dynamic wallpaper: a set of pictures that changes through
the day. A still picture (Surf Settings → Look → Wallpaper → *Picture*, or `surfctl wallpaper set NAME`)
or your own image, when you set one, always wins. See [dynamic-wallpapers.md](dynamic-wallpapers.md).

The still pictures are surfd's own gradient wallpapers (Tide, Driftwood, Kelp and Dusk, dark and light,
in 16:9, 16:10 and ultrawide sizes; pick the size that matches your screen) and 18 images by other artists.
Pictures you put in `~/.local/share/surfd/wallpapers/static/` are listed first.

Every one of these wallpapers also has a theme with colours picked from it (`surfctl theme list`): choosing
the theme switches to its picture or dynamic wallpaper. The dynamic ones have a light and a dark style.

```sh
surfctl wallpaper status                    # what is showing, and every frame of the set
surfctl wallpaper list                      # theme wallpapers, dynamic sets and the still pictures
surfctl wallpaper set tide-dark-3840x2160   # a still picture by name (wins over the dynamic one)
surfctl wallpaper dynamic cyprus            # pick a set (or "off" for the theme's wallpaper)
surfctl wallpaper sync auto                 # follow the time of day (the sun, for "cyprus")
surfctl wallpaper sync theme                # lightest frame in light style, darkest in dark style
surfctl wallpaper sync frame noon           # keep one frame, by number or part of its name
surfctl wallpaper location 35.2 33.4        # where you are, for sets that follow the sun
```

## Login screen

The login screen uses the default theme. To give it your current theme and
wallpaper:

```sh
sudo surfctl greeter sync
```

(or **System → Use this theme on the login screen** in Surf Settings).

## Weak dependencies

surfd keeps installs lean: `dnf` does not pull in "recommended" packages
automatically (`/usr/share/dnf5/libdnf.conf.d/20-surfd.conf`). Install a
recommended package by name when you want it, or return to Fedora's
behaviour:

```sh
printf '[main]\ninstall_weak_deps=True\n' | sudo tee /etc/dnf/libdnf5.conf.d/90-weakdeps.conf
```

## Files at a glance

| Path | What |
|---|---|
| `~/.config/surfd/surfd.toml` | your settings |
| `~/.config/surfd/sway.d/*.conf` | raw Sway additions |
| `~/.local/share/surfd/themes/` | your theme packs |
| `~/.local/state/surfd/generated/` | generated Sway/Waybar config (don't edit) |
| `~/.local/state/surfd/backups/` | backups made by reset/restore |
| `~/.local/state/surfd/session.log` | log of the current session (`.old`: previous) |
| `/usr/share/surfd/defaults/surfd.toml` | the defaults |
| `/usr/share/surfd/themes/` | built-in theme packs |
| `/etc/surfd/sway.d/*.conf` | system-wide Sway additions (admins) |
| `/etc/surfd/greetd/` | login screen |
