"""surfctl — change the surfd desktop from the command line.

Every change edits ~/.config/surfd/surfd.toml (comments preserved),
regenerates the app configs and, inside a running session, applies them
immediately. Run `surfctl <command> --help` for details.
"""

from __future__ import annotations

import argparse
import os
import pwd
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import __version__, config, dynwall, generate, keys, paths, schema, session, system, themes

BAR_PRESETS: dict[str, dict[str, list[str]]] = {
    "default": {"left": ["workspaces", "mode", "window"], "center": ["clock"],
                "right": ["tray", "network", "audio", "battery", "power"]},
    "minimal": {"left": ["workspaces"], "center": ["clock"], "right": ["audio", "battery"]},
    "classic": {"left": ["workspaces", "taskbar"], "center": [],
                "right": ["tray", "network", "audio", "battery", "clock", "power"]},
    "full": {"left": ["workspaces", "mode", "window"], "center": ["clock", "media"],
             "right": ["tray", "idle", "cpu", "memory", "temperature", "network", "bluetooth",
                       "audio", "backlight", "battery", "keyboard", "power"]},
}

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def ok(msg: str) -> None:
    print(_c("32", "✓") + " " + msg)


def info(msg: str) -> None:
    print(_c("2", msg))


def fail(msg: str) -> int:
    print(_c("31", "error:") + " " + msg, file=sys.stderr)
    return 1


# ------------------------------------------------------------ the change path --

def apply_changes(changes: dict[str, Any], args: argparse.Namespace, summary: str) -> int:
    """Validate + write config, regenerate, reload. Rolls back on failure."""
    user_file = paths.user_config()
    config.ensure_user_config()
    previous = user_file.read_text(encoding="utf-8")
    try:
        config.set_values(changes)
        ctx = generate.build_context()
        _, actions = session.regenerate_and_reload(ctx, reload=not getattr(args, "no_reload", False))
    except (config.ConfigError, themes.ThemeError, keys.BindingError, RuntimeError) as e:
        config._atomic_write(user_file, previous)
        return fail(f"{e}\n(no changes were made)")
    if session.in_sway() and not getattr(args, "no_reload", False):
        ok(summary + " — applied")
    else:
        ok(summary + " — saved; applies at next login (or run `surfctl reload`)")
    for a in actions:
        if "FAILED" in a:
            print(_c("33", "  " + a))
    return 0


def regenerate(args: argparse.Namespace, summary: str) -> int:
    try:
        ctx = generate.build_context()
        report, actions = session.regenerate_and_reload(ctx, reload=not getattr(args, "no_reload", False))
    except (config.ConfigError, themes.ThemeError, keys.BindingError, RuntimeError) as e:
        return fail(str(e))
    ok(summary)
    for p in report.skipped:
        info(f"  left alone (you took it over): {p}")
    for a in actions:
        if "FAILED" in a:
            print(_c("33", "  " + a))
    return 0


# ----------------------------------------------------------------- commands --

def cmd_init(args: argparse.Namespace) -> int:
    existed = paths.user_config().exists()
    try:
        path = config.ensure_user_config()
    except config.ConfigError as e:
        return fail(str(e))
    if not existed:
        kb = system.system_keyboard()
        seed = {f"input.keyboard_{k}": v for k, v in kb.items()}
        if seed:
            try:
                config.set_values(seed, validate_result=False)
            except config.ConfigError:
                pass
        if not args.quiet:
            ok(f"created {path}")
    elif not args.quiet:
        info(f"{path} already exists")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    try:
        ctx = generate.build_context()
    except (config.ConfigError, themes.ThemeError, keys.BindingError) as e:
        return fail(str(e))
    if args.print:
        wanted = {o.path.name: o for o in generate.outputs(ctx)}
        wanted.update({str(o.path.relative_to(o.path.parent.parent)): o for o in generate.outputs(ctx)})
        if args.print not in wanted:
            return fail(f"unknown file '{args.print}'. Choose from: {', '.join(sorted(wanted))}")
        sys.stdout.write(wanted[args.print].content)
        return 0
    errs = config.errors(config.validate(ctx.cfg))
    if errs:
        return fail("; ".join(map(str, errs)))
    ok_sway, msg = session.validate_sway_config(generate.sway(ctx))
    if not ok_sway:
        return fail("generated Sway config failed validation:\n" + msg)
    report = generate.write_all(ctx, dry_run=args.dry_run)
    if not args.quiet:
        verb = "would write" if args.dry_run else "wrote"
        ok(f"{verb} {len(report.written)} file(s), {len(report.unchanged)} unchanged")
        for p in report.skipped:
            info(f"  left alone (you took it over): {p}")
    return 0


def cmd_reload(args: argparse.Namespace) -> int:
    return regenerate(args, "desktop reloaded" if session.in_sway() else "configs regenerated (no running session)")


def cmd_apply(args: argparse.Namespace) -> int:
    try:
        ctx = generate.build_context()
    except (config.ConfigError, themes.ThemeError) as e:
        return fail(str(e))
    if args.desktop_settings:
        session.desktop_settings(ctx)
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    try:
        cfg = config.load()
    except config.ConfigError as e:
        return fail(str(e))
    value = config.get(cfg, args.key)
    if value is None:
        return fail(f"no setting '{args.key}'")
    if isinstance(value, dict):
        for k, v in value.items():
            print(f"{k} = {v!r}" if not isinstance(v, dict) else f"[{args.key}.{k}]")
    elif isinstance(value, list):
        print(",".join(map(str, value)))
    elif isinstance(value, bool):
        print("true" if value else "false")
    else:
        print(value)
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    value: Any = " ".join(args.value)
    return apply_changes({args.key: value}, args, f"{args.key} = {value}")


def cmd_explain(args: argparse.Namespace) -> int:
    try:
        cfg = config.load()
    except config.ConfigError:
        cfg = {}
    prefix = args.key or ""
    for dotted, fld in schema.SCHEMA.items():
        if not dotted.startswith(prefix):
            continue
        current = config.get(cfg, dotted)
        extra = f" ({' | '.join(fld.choices)})" if fld.choices else ""
        print(_c("1", dotted) + _c("2", f"  = {current!r}"))
        print(f"    {fld.help}{extra}")
    return 0


def cmd_theme(args: argparse.Namespace) -> int:
    sub = args.theme_cmd
    if sub in (None, "list"):
        try:
            current = config.load()["theme"]["name"]
        except (config.ConfigError, KeyError):
            current = ""
        found, problems = themes.discover()
        for t in found:
            mark = _c("32", "●") if t.name == current else " "
            where = "system" if t.is_system else "user"
            print(f"{mark} {t.name:<14} {t.title:<16} {'/'.join(t.variants):<11} {where:<6} {t.meta.get('description', '')}")
        for p in problems:
            print(_c("33", "  broken: ") + p)
        return 0
    if sub == "set":
        changes: dict[str, Any] = {"theme.name": args.name}
        if args.variant:
            changes["theme.variant"] = args.variant
        if themes.find(args.name) is None:
            return fail(f"theme '{args.name}' not found (installed: {', '.join(themes.names())})")
        return apply_changes(changes, args, f"theme set to {args.name}")
    if sub == "variant":
        variant = args.variant
        if variant == "toggle":
            variant = "light" if config.load()["theme"]["variant"] == "dark" else "dark"
        return apply_changes({"theme.variant": variant}, args, f"style set to {variant}")
    if sub == "info":
        name = args.name or config.load()["theme"]["name"]
        t = themes.find(name)
        if t is None:
            return fail(f"theme '{name}' not found")
        print(f"{t.title} ({t.name}) — {t.meta.get('description', '')}")
        print(f"  path:     {t.path}")
        print(f"  author:   {t.meta.get('author', '?')}   license: {t.meta.get('license', '?')}")
        for v in t.variants:
            pal = t.palette(v)
            print(f"  {v:<6} accent {pal.accent}  background {pal.background}  wallpaper {t.wallpaper(v)}")
        for p in t.problems:
            print(_c("33", "  warning: ") + p)
        return 0
    if sub == "install":
        try:
            t = themes.install(Path(args.source), force=args.force)
        except themes.ThemeError as e:
            return fail(str(e))
        ok(f"installed theme '{t.name}' to {t.path}  (use: surfctl theme set {t.name})")
        return 0
    if sub == "export":
        try:
            out = themes.export(args.name, Path(args.output))
        except themes.ThemeError as e:
            return fail(str(e))
        ok(f"exported to {out}")
        return 0
    if sub == "new":
        try:
            dest = themes.new(args.name, args.base)
        except themes.ThemeError as e:
            return fail(str(e))
        ok(f"created {dest} from '{args.base}'. Edit theme.toml, then: surfctl theme set {args.name}")
        return 0
    return fail(f"unknown theme command {sub}")


def cmd_accent(args: argparse.Namespace) -> int:
    value = "" if args.color in ("reset", "default") else args.color
    return apply_changes({"theme.accent": value}, args,
                         "accent reset to theme default" if not value else f"accent set to {value}")


def _wallpaper_status() -> int:
    ctx = generate.build_context()
    sets = dynwall.discover()
    name = ctx.c("wallpaper.dynamic") or ""
    if ctx.custom_wallpaper is not None:
        print(f"showing your own image: {ctx.custom_wallpaper}")
        if name:
            info(f"(dynamic wallpaper '{name}' is set but your image wins; `surfctl wallpaper dynamic {name}` switches to it)")
        return 0
    if ctx.dynamic is None:
        print(f"showing the theme's wallpaper: {ctx.wallpaper}")
        if name:
            info(f"dynamic wallpaper '{name}' is not installed (installed: {', '.join(sets) or 'none'})")
        return 0
    dset, shown = ctx.dynamic
    sync = ctx.c("wallpaper.sync") or "auto"
    print(f"dynamic wallpaper: {dset.title} ({dset.name}, {dset.kind} based)   follows: {sync}   "
          f"style: {ctx.pal.variant}")
    for i, f in enumerate(dset.frames):
        when = f"{f.at // 60:02d}:{f.at % 60:02d}" if f.at is not None else f"sun {f.altitude:+.0f} deg, azimuth {f.azimuth:.0f}"
        tags = (" lightest" if f.file == dset.light else "") + (" darkest" if f.file == dset.dark else "")
        print(f"  {i}  {f.file.name:<26} {when}{tags}{'   <-- showing' if f.file == shown else ''}")
    return 0


def cmd_wallpaper(args: argparse.Namespace) -> int:
    sub = args.wp_cmd
    if sub == "set":
        p = Path(args.path).expanduser().resolve()
        if not p.is_file():
            return fail(f"no such file: {args.path}")
        changes: dict[str, Any] = {"wallpaper.path": str(p)}
        if args.mode:
            changes["wallpaper.mode"] = args.mode
        return apply_changes(changes, args, f"wallpaper set to {p.name}")
    if sub == "reset":
        default = dynwall.find(dynwall.DEFAULT_SET)
        changes = {"wallpaper.path": "", "wallpaper.dynamic": dynwall.DEFAULT_SET, "wallpaper.sync": "auto",
                   "wallpaper.frame": ""}
        what = f"{default.title}, follows the time of day" if default else "the theme's wallpaper"
        return apply_changes(changes, args, f"wallpaper reset to the default ({what})")
    if sub == "dynamic":
        if args.name in ("off", "none", ""):
            return apply_changes({"wallpaper.dynamic": ""}, args, "dynamic wallpaper turned off")
        sets = dynwall.discover()
        if args.name not in sets:
            return fail(f"no dynamic wallpaper '{args.name}' (installed: {', '.join(sets) or 'none'}; `surfctl wallpaper list`)")
        return apply_changes({"wallpaper.dynamic": args.name, "wallpaper.path": ""}, args,
                             f"dynamic wallpaper set to {sets[args.name].title}")
    if sub == "sync":
        changes = {"wallpaper.sync": args.mode_name}
        if args.mode_name == "frame":
            if not args.frame:
                return fail("which frame? e.g. `surfctl wallpaper sync frame noon` (see `surfctl wallpaper status`)")
            ctx = generate.build_context()
            if ctx.dynamic is None or dynwall.named_frame(ctx.dynamic[0], args.frame) is None:
                return fail(f"'{args.frame}' is not exactly one frame of the dynamic wallpaper (see `surfctl wallpaper status`)")
            changes["wallpaper.frame"] = args.frame
        words = {"auto": "follows the time of day", "theme": "follows the light/dark style",
                 "frame": f"stays on frame '{args.frame}'"}
        return apply_changes(changes, args, f"dynamic wallpaper {words[args.mode_name]}")
    if sub == "location":
        value = "" if args.place in ("auto", "guess") else f"{args.place}, {args.longitude}" if args.longitude else args.place
        try:
            dynwall.parse_location(value)
        except dynwall.DynError as e:
            return fail(str(e))
        return apply_changes({"wallpaper.location": value}, args,
                             f"location set to {value}" if value else "location will be guessed from the time zone")
    if sub == "status":
        return _wallpaper_status()
    if sub == "apply":  # used by scripts: show the frame for this moment now
        return session.wallpaper_daemon(once=True)
    if sub == "daemon":  # started by the session (libexec/surfd-dynwall); not for people
        return session.wallpaper_daemon()
    if sub in ("list", None):
        found, _ = themes.discover()
        for t in found:
            for v in t.variants:
                wp = t.wallpaper(v)
                if wp:
                    print(f"{t.name}/{v}: {wp}")
        for dset in dynwall.discover().values():
            print(f"dynamic {dset.name}: {dset.title}, {len(dset.frames)} frames, {dset.kind} based")
        extra = paths.system_dir() / "wallpapers"
        if extra.is_dir():
            for f in sorted(extra.iterdir()):
                if f.is_file():
                    print(f"extra: {f}")
        return 0
    return fail(f"unknown wallpaper command {sub}")


def cmd_font(args: argparse.Namespace) -> int:
    key = "fonts.ui" if args.which == "ui" else "fonts.mono"
    changes: dict[str, Any] = {key: args.family}
    if args.size:
        changes["fonts.size" if args.which == "ui" else "fonts.mono_size"] = args.size
    return apply_changes(changes, args, f"{args.which} font set to {args.family}")


def cmd_gaps(args: argparse.Namespace) -> int:
    changes: dict[str, Any] = {"layout.gaps_inner": args.inner}
    if args.outer is not None:
        changes["layout.gaps_outer"] = args.outer
    return apply_changes(changes, args, "gaps updated")


def cmd_radius(args: argparse.Namespace) -> int:
    return apply_changes({"layout.radius": args.value}, args, f"corner radius set to {args.value}")


def cmd_mode(args: argparse.Namespace) -> int:
    return apply_changes({"layout.mode": args.mode}, args, f"window mode set to {args.mode}")


def parse_bar_layout(spec: list[str]) -> dict[str, list[str]]:
    """'left=workspaces,mode center=clock right=tray,audio' -> dict."""
    result: dict[str, list[str]] = {}
    for part in spec:
        if "=" not in part:
            raise config.ConfigError(f"'{part}': expected left=..., center=... or right=...")
        side, _, mods = part.partition("=")
        side = {"centre": "center", "middle": "center"}.get(side.strip(), side.strip())
        if side not in ("left", "center", "right"):
            raise config.ConfigError(f"'{side}' is not a bar side (left, center, right)")
        result[side] = [m.strip() for m in mods.split(",") if m.strip()]
    return result


def cmd_bar(args: argparse.Namespace) -> int:
    sub = args.bar_cmd
    if sub == "modules":
        for name, desc in schema.BAR_MODULES.items():
            print(f"  {name:<12} {desc}")
        print("\nPresets: " + ", ".join(BAR_PRESETS))
        return 0
    if sub == "layout":
        try:
            sides = parse_bar_layout(args.spec)
        except config.ConfigError as e:
            return fail(str(e))
        return apply_changes({f"bar.{k}": v for k, v in sides.items()}, args, "bar layout updated")
    if sub == "preset":
        if args.name not in BAR_PRESETS:
            return fail(f"unknown preset '{args.name}' (have: {', '.join(BAR_PRESETS)})")
        return apply_changes({f"bar.{k}": v for k, v in BAR_PRESETS[args.name].items()}, args,
                             f"bar preset '{args.name}' applied")
    if sub == "position":
        return apply_changes({"bar.position": args.where}, args, f"bar moved to the {args.where}")
    if sub == "style":
        return apply_changes({"bar.style": args.style}, args, f"bar style set to {args.style}")
    cfg = config.load()
    for side in ("left", "center", "right"):
        print(f"{side:<7} {', '.join(cfg['bar'][side]) or '-'}")
    return 0


def cmd_keys(args: argparse.Namespace) -> int:
    sub = args.keys_cmd
    if sub == "actions":
        for name, a in keys.ACTIONS.items():
            print(f"  {name:<22} {a.description}")
        print("\n  focus|move left|right|up|down, workspace N, move-to-workspace N,")
        print("  exec <command>, sway <sway command>, none (disable)")
        return 0
    if sub == "bind":
        action = " ".join(args.action)
        if not action:
            return fail("missing action (see: surfctl keys actions)")
        try:
            keys.normalize_combo(args.combo, config.load()["keys"]["modifier"])
            keys.resolve_action(action, config.load()["apps"])
        except keys.BindingError as e:
            return fail(str(e))
        return apply_changes({f"keys.bindings.{args.combo}": action}, args, f"{args.combo} → {action}")
    if sub == "unbind":
        return apply_changes({f"keys.bindings.{args.combo}": "none"}, args, f"{args.combo} unbound")
    try:
        rows = keys.cheatsheet_lines(config.load())
    except (config.ConfigError, keys.BindingError) as e:
        return fail(str(e))
    width = max(len(k) for _, k, _ in rows) + 2
    last = ""
    for cat, combo, desc in rows:
        if cat != last:
            print(_c("1", f"\n{cat}"))
            last = cat
        print(f"  {combo.ljust(width)}{desc}")
    return 0


def cmd_apps(args: argparse.Namespace) -> int:
    if args.apps_cmd == "set":
        if not args.command:
            return fail("missing command")
        return apply_changes({f"apps.{args.role}": " ".join(args.command)}, args,
                             f"{args.role} set to {' '.join(args.command)}")
    for role, cmd in config.load()["apps"].items():
        print(f"  {role:<10} {cmd}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    what = f"[{args.section}]" if args.section else "your whole surfd.toml"
    if not args.yes:
        if not sys.stdin.isatty():
            return fail("refusing to reset without --yes when not interactive")
        answer = input(f"Reset {what} to the defaults? A backup is kept. [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            info("nothing changed")
            return 0
    try:
        saved = config.reset(args.section)
    except config.ConfigError as e:
        return fail(str(e))
    if saved:
        info(f"backup: {saved}  (undo with: surfctl backups restore latest)")
    return regenerate(args, f"{what} reset to defaults")


def cmd_backups(args: argparse.Namespace) -> int:
    backups = config.list_backups()
    if args.backups_cmd == "restore":
        target = backups[0] if args.which == "latest" and backups else Path(args.which).expanduser()
        try:
            saved = config.restore(target)
        except config.ConfigError as e:
            return fail(str(e))
        if saved:
            info(f"current file saved as {saved}")
        return regenerate(args, f"restored {target.name}")
    if not backups:
        info("no backups yet (they are made before every reset/restore)")
    for b in backups:
        print(b)
    return 0


REQUIRED_BINARIES = ["sway", "waybar", "fuzzel", "mako", "makoctl", "foot", "swaybg", "swaylock",
                     "swayidle", "grim", "slurp", "wl-copy", "wpctl", "brightnessctl", "playerctl", "gsettings"]


def cmd_doctor(args: argparse.Namespace) -> int:
    if getattr(args, "quiet", False):
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            return _doctor(args)
    return _doctor(args)


def _doctor(args: argparse.Namespace) -> int:
    problems = 0

    def report(level: str, msg: str) -> None:
        nonlocal problems
        if level == "error":
            problems += 1
            print(_c("31", "  ✗ ") + msg)
        elif level == "warning":
            print(_c("33", "  ! ") + msg)
        else:
            print(_c("32", "  ✓ ") + msg)

    print(_c("1", "Themes"))
    found, broken = themes.discover()
    report("ok" if found else "error", f"{len(found)} theme(s): {', '.join(t.name for t in found)}")
    for b in broken:
        report("error", b)
    for t in found:
        for p in t.problems:
            report("warning", f"{t.name}: {p}")

    print(_c("1", "Configuration"))
    try:
        cfg = config.load_defaults() if args.system else config.load()
        report("ok", f"loaded {'system defaults' if args.system else paths.user_config()}")
        for p in config.validate(cfg):
            report(p.level, str(p).split(": ", 1)[1])
        if not config.errors(config.validate(cfg)):
            ctx = generate.build_context(cfg)
            okay, msg = session.validate_sway_config(generate.sway(ctx))
            report("ok" if okay else "error", "generated Sway config " + ("is valid" if okay else "is INVALID:\n" + msg))
    except (config.ConfigError, themes.ThemeError, keys.BindingError) as e:
        report("error", str(e))

    if not args.system:
        print(_c("1", "Programs"))
        missing = [b for b in REQUIRED_BINARIES if shutil.which(b) is None]
        report("warning" if missing else "ok", f"missing: {', '.join(missing)}" if missing else "all session programs found")
        print(_c("1", "Hand-edited files (surfctl leaves these alone)"))
        try:
            taken = [o.path for o in generate.outputs(generate.build_context())
                     if o.managed and o.path.exists() and not generate._is_ours(o.path)]
        except Exception:
            taken = []
        report("ok", "none" if not taken else ", ".join(map(str, taken)))

    if args.notify and problems:
        session.notify("surfd configuration problem",
                       f"{problems} problem(s) in surfd.toml. Run `surfctl doctor` in a terminal.",
                       urgency_critical=True, timeout_ms=0)
    return 1 if problems else 0


def cmd_cheatsheet(args: argparse.Namespace) -> int:
    try:
        ctx = generate.build_context()
    except (config.ConfigError, themes.ThemeError, keys.BindingError) as e:
        return fail(str(e))
    if args.print or not shutil.which("fuzzel"):
        return cmd_keys(argparse.Namespace(keys_cmd="list"))
    session.cheatsheet(ctx)
    return 0


def cmd_power_menu(args: argparse.Namespace) -> int:
    session.power_menu()
    return 0


def cmd_network_menu(args: argparse.Namespace) -> int:
    session.network_menu()
    return 0


def cmd_lock(args: argparse.Namespace) -> int:
    session.lock()
    return 0


def cmd_screenshot(args: argparse.Namespace) -> int:
    path = session.screenshot(args.mode)
    if path:
        print(path)
    return 0


def cmd_first_run(args: argparse.Namespace) -> int:
    marker = paths.user_config_dir() / ".welcome-done"
    if marker.exists() and not args.force:
        return 0
    if shutil.which("surf-welcome"):
        subprocess.Popen(["surf-welcome"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def cmd_greeter(args: argparse.Namespace) -> int:
    if os.geteuid() != 0:
        return fail("run with sudo: sudo surfctl greeter sync")
    user = os.environ.get("SUDO_USER")
    if not user and os.environ.get("PKEXEC_UID"):  # launched from Surf Settings via pkexec
        user = pwd.getpwuid(int(os.environ["PKEXEC_UID"])).pw_name
    if not user or user == "root":
        return fail("run as your user via sudo, so your theme can be read")
    home = pwd.getpwnam(user).pw_dir
    os.environ["HOME"] = home
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        os.environ.pop(var, None)
    try:
        ctx = generate.build_context()
    except (config.ConfigError, themes.ThemeError, keys.BindingError) as e:
        return fail(str(e))
    dest = Path(os.environ.get("SURFD_GREETER_DIR", "/etc/surfd/greetd"))
    dest.mkdir(parents=True, exist_ok=True)
    background = dest / "background"
    wp = ctx.wallpaper
    if wp is not None and wp.suffix.lower() != ".svg":
        shutil.copyfile(wp, background)
        os.chmod(background, 0o644)
    (dest / "style.css").write_text(generate.greeter_css(ctx, str(background)), encoding="utf-8")
    os.chmod(dest / "style.css", 0o644)
    if shutil.which("restorecon"):
        subprocess.run(["restorecon", "-R", str(dest)], check=False)
    ok(f"login screen now uses {user}'s theme ({ctx.theme.name}, {ctx.pal.variant}); shown at next login")
    return 0


def cmd_path(args: argparse.Namespace) -> int:
    table: dict[str, Path] = {
        "config": paths.user_config(),
        "defaults": paths.system_defaults(),
        "generated": paths.generated_dir(),
        "themes": paths.user_themes_dir(),
        "system-themes": paths.system_themes_dir(),
        "backups": paths.backups_dir(),
        "sway.d": paths.user_config_dir() / "sway.d",
    }
    if args.what:
        print(table[args.what])
    else:
        for k, v in table.items():
            print(f"{k:<14} {v}")
    return 0


# -------------------------------------------------------------------- parser --

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="surfctl",
        description="Change the surfd desktop. Edits ~/.config/surfd/surfd.toml and applies it live.",
        epilog="Examples:\n"
               "  surfctl theme set driftwood --variant light\n"
               "  surfctl accent '#88c0d0'\n"
               "  surfctl wallpaper set ~/Pictures/beach.jpg\n"
               "  surfctl bar layout left=workspaces center=clock right=tray,audio,power\n"
               "  surfctl keys bind Mod+F1 exec foot -e htop\n"
               "  surfctl reset            (everything back to defaults; a backup is kept)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"surfctl {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    def add(name: str, func: Callable[[argparse.Namespace], int], help_: str, *, live: bool = False,
            aliases: tuple[str, ...] = ()) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_, description=help_, aliases=list(aliases))
        sp.set_defaults(func=func)
        if live:
            sp.add_argument("--no-reload", action="store_true", help="write files but don't touch the running session")
        return sp

    sp = add("init", cmd_init, "create ~/.config/surfd/surfd.toml from the defaults")
    sp.add_argument("-q", "--quiet", action="store_true")

    sp = add("generate", cmd_generate, "regenerate all app configs from surfd.toml (no live reload)")
    sp.add_argument("-n", "--dry-run", action="store_true", help="show what would change")
    sp.add_argument("-q", "--quiet", action="store_true")
    sp.add_argument("--print", metavar="FILE", help="print one generated file (e.g. sway/config) to stdout")

    add("reload", cmd_reload, "regenerate and apply to the running session", live=True)

    sp = add("apply", cmd_apply, argparse.SUPPRESS)
    sp.add_argument("--desktop-settings", action="store_true")

    sp = add("get", cmd_get, "print a setting, e.g. surfctl get theme.accent")
    sp.add_argument("key")
    sp = add("set", cmd_set, "change any setting, e.g. surfctl set layout.gaps_inner 12", live=True)
    sp.add_argument("key")
    sp.add_argument("value", nargs="+")
    sp = add("explain", cmd_explain, "list settings with their current values and help")
    sp.add_argument("key", nargs="?", help="setting or section prefix, e.g. 'bar'")

    tp = add("theme", cmd_theme, "list, switch, install and share theme packs")
    tsub = tp.add_subparsers(dest="theme_cmd", metavar="<action>")
    tsub.add_parser("list", help="installed themes")
    s = tsub.add_parser("set", help="switch theme")
    s.add_argument("name")
    s.add_argument("--variant", choices=("dark", "light"))
    s.add_argument("--no-reload", action="store_true")
    s = tsub.add_parser("variant", help="dark, light or toggle")
    s.add_argument("variant", choices=("dark", "light", "toggle"))
    s.add_argument("--no-reload", action="store_true")
    s = tsub.add_parser("info", help="details about a theme")
    s.add_argument("name", nargs="?")
    s = tsub.add_parser("install", help="install a theme folder, .tar.gz or .zip")
    s.add_argument("source")
    s.add_argument("--force", action="store_true", help="replace an existing user theme")
    s = tsub.add_parser("export", help="pack a theme as .tar.gz to share")
    s.add_argument("name")
    s.add_argument("output", nargs="?", default=".")
    s = tsub.add_parser("new", help="start a new theme by copying another")
    s.add_argument("name")
    s.add_argument("--from", dest="base", default="tide")

    sp = add("accent", cmd_accent, "set the accent colour (#rrggbb) or 'reset'", live=True)
    sp.add_argument("color")

    wp = add("wallpaper", cmd_wallpaper, "set or reset the wallpaper")
    wsub = wp.add_subparsers(dest="wp_cmd", metavar="<action>")
    s = wsub.add_parser("set", help="use an image file")
    s.add_argument("path")
    s.add_argument("--mode", choices=("fill", "fit", "center", "tile", "stretch"))
    s.add_argument("--no-reload", action="store_true")
    s = wsub.add_parser("reset", help="back to the default wallpaper (the dynamic one that follows the time of day)")
    s.add_argument("--no-reload", action="store_true")
    s = wsub.add_parser("dynamic", help="use a time-of-day wallpaper (or 'off'); see `list`")
    s.add_argument("name")
    s.add_argument("--no-reload", action="store_true")
    s = wsub.add_parser("sync", help="what the dynamic wallpaper follows: auto (time of day), theme (light/dark), frame <n>")
    s.add_argument("mode_name", choices=dynwall.SYNC_MODES, metavar="{auto,theme,frame}")
    s.add_argument("frame", nargs="?", help="with 'frame': its number or part of its file name (see `status`)")
    s.add_argument("--no-reload", action="store_true")
    s = wsub.add_parser("location", help="where you are, for sets that follow the sun: <latitude> <longitude> or 'auto'")
    s.add_argument("place", help="latitude, or 'auto'")
    s.add_argument("longitude", nargs="?")
    s.add_argument("--no-reload", action="store_true")
    wsub.add_parser("status", help="which wallpaper and frame are showing, and all frames of the dynamic one")
    wsub.add_parser("list", help="wallpapers shipped with themes and the dynamic ones")
    wsub.add_parser("apply", help=argparse.SUPPRESS)
    wsub.add_parser("daemon", help=argparse.SUPPRESS)

    sp = add("font", cmd_font, "set the interface or monospace font", live=True)
    sp.add_argument("which", choices=("ui", "mono"))
    sp.add_argument("family")
    sp.add_argument("size", nargs="?", type=int)

    sp = add("gaps", cmd_gaps, "set window gaps: surfctl gaps <inner> [outer]", live=True)
    sp.add_argument("inner", type=int)
    sp.add_argument("outer", nargs="?", type=int)
    sp = add("radius", cmd_radius, "corner radius for bar, notifications, launcher", live=True)
    sp.add_argument("value", type=int)
    sp = add("mode", cmd_mode, "tiling, or floating (mouse-friendly)", live=True)
    sp.add_argument("mode", choices=("tiling", "floating"))

    bp = add("bar", cmd_bar, "bar layout, position, style and presets")
    bsub = bp.add_subparsers(dest="bar_cmd", metavar="<action>")
    s = bsub.add_parser("layout", help="e.g. left=workspaces,mode center=clock right=tray,audio")
    s.add_argument("spec", nargs="+")
    s.add_argument("--no-reload", action="store_true")
    s = bsub.add_parser("preset", help="default, minimal, classic or full")
    s.add_argument("name")
    s.add_argument("--no-reload", action="store_true")
    s = bsub.add_parser("position", help="top or bottom")
    s.add_argument("where", choices=("top", "bottom"))
    s.add_argument("--no-reload", action="store_true")
    s = bsub.add_parser("style", help="floating or docked")
    s.add_argument("style", choices=("floating", "docked"))
    s.add_argument("--no-reload", action="store_true")
    bsub.add_parser("modules", help="available modules")

    kp = add("keys", cmd_keys, "list, add and remove key bindings")
    ksub = kp.add_subparsers(dest="keys_cmd", metavar="<action>")
    ksub.add_parser("list", help="current bindings")
    ksub.add_parser("actions", help="actions you can bind")
    s = ksub.add_parser("bind", help="e.g. surfctl keys bind Mod+F1 exec foot -e htop")
    s.add_argument("--no-reload", action="store_true")
    s.add_argument("combo")
    s.add_argument("action", nargs=argparse.REMAINDER, help="action and its arguments")
    s = ksub.add_parser("unbind", help="disable a binding")
    s.add_argument("combo")
    s.add_argument("--no-reload", action="store_true")

    ap = add("apps", cmd_apps, "default apps (terminal, launcher, browser, files, editor)")
    asub = ap.add_subparsers(dest="apps_cmd", metavar="<action>")
    asub.add_parser("list")
    s = asub.add_parser("set", help="e.g. surfctl apps set browser flatpak run org.mozilla.firefox")
    s.add_argument("--no-reload", action="store_true")
    s.add_argument("role", choices=("terminal", "launcher", "browser", "files", "editor"))
    s.add_argument("command", nargs=argparse.REMAINDER, help="command and its arguments")

    sp = add("reset", cmd_reset, "reset everything (or one section) to defaults; keeps a backup", live=True)
    sp.add_argument("section", nargs="?", help="e.g. theme, bar, keys")
    sp.add_argument("-y", "--yes", action="store_true", help="don't ask")

    bk = add("backups", cmd_backups, "list or restore surfd.toml backups")
    bksub = bk.add_subparsers(dest="backups_cmd", metavar="<action>")
    bksub.add_parser("list")
    s = bksub.add_parser("restore", help="restore a backup file, or 'latest'")
    s.add_argument("which")
    s.add_argument("--no-reload", action="store_true")

    sp = add("doctor", cmd_doctor, "check configuration, themes and programs")
    sp.add_argument("--system", action="store_true", help="check only system defaults and themes")
    sp.add_argument("--notify", action="store_true", help="send a notification if something is wrong")
    sp.add_argument("-q", "--quiet", action="store_true", help="only the exit status (and --notify)")

    sp = add("cheatsheet", cmd_cheatsheet, "searchable key binding cheat sheet (Super+/)")
    sp.add_argument("--print", action="store_true", help="print instead of opening the launcher")
    add("power-menu", cmd_power_menu, "lock, log out, suspend, restart, shut down")
    add("network-menu", cmd_network_menu, "pick a Wi-Fi network (used by the bar)")
    add("lock", cmd_lock, "lock the screen")
    sp = add("screenshot", cmd_screenshot, "save a screenshot to ~/Pictures/Screenshots and the clipboard")
    sp.add_argument("mode", choices=("full", "area"), nargs="?", default="full")
    sp = add("first-run", cmd_first_run, argparse.SUPPRESS)
    sp.add_argument("--force", action="store_true")

    gp = add("greeter", cmd_greeter, "copy your theme to the login screen (needs sudo)")
    gsub = gp.add_subparsers(dest="greeter_cmd", metavar="<action>", required=True)
    gsub.add_parser("sync")

    sp = add("path", cmd_path, "show where surfd keeps things")
    sp.add_argument("what", nargs="?", choices=("config", "defaults", "generated", "themes", "system-themes",
                                                "backups", "sway.d"))
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    # Commands that read user config create it on first use.
    if args.command not in ("init", "path", "doctor", "greeter") and not paths.user_config().exists():
        try:
            config.ensure_user_config()
        except config.ConfigError as e:
            return fail(str(e))
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except (config.ConfigError, themes.ThemeError, keys.BindingError, schema.SchemaError) as e:
        return fail(str(e))
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
