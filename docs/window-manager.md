# Why Sway (and not Hyprland or river)

surfd needs a compositor that is small, stable across Fedora releases, safe
with SELinux enforcing, and easy to drive from generated configuration.
Sway fits all four.

| | **Sway** | Hyprland | river |
|---|---|---|---|
| Maturity | Since 2016; 1.x stable, i3-compatible config | Fast-moving; config syntax and IPC change between releases | Pre-1.0; layout protocol still evolving |
| In Fedora | Official packages, an official **Fedora Sway spin** and Sway Atomic | Packaged; follows a fast upstream | Packaged; smaller user base |
| Resource use | Small; software (pixman) rendering fallback when there is no GPU | Higher; GPU effects by design | Very small |
| Config model | Declarative text + rich IPC (`swaymsg`); `sway --validate` checks a config before it is used | Declarative text + IPC; options change between releases | Configured by an *executable* init script, layouts are separate programs |
| Ecosystem | Waybar, swaylock/swayidle, xdg-desktop-portal-wlr, i3 documentation applies | Own ecosystem (hyprlock, hypridle, portal) | Smaller; layout generators |
| Eye candy | None (no animations, square borders) | Animations, blur, rounded corners | None |

### What decided it

1. **Stability is the feature.** surfd regenerates the compositor config on
   every change. Sway's config language has been stable for years, and
   `sway --validate` lets surfctl refuse a broken config *before* it touches
   your session. Hyprland's frequent breaking changes would turn every Fedora
   update into a surfctl update.
2. **Fedora maintains it.** Sway is a first-class Fedora desktop with a SIG,
   an official spin and an atomic variant. Bugs get fixed in Fedora, not just upstream.
3. **Lightweight and robust.** Sway runs fine on old GPUs and in VMs without
   3D; the 400 MB idle target is realistic.
4. **Generatable.** A flat, declarative config maps 1:1 from `surfd.toml`.
   river's executable init model would need a different design.

### The price, and how surfd softens it

- **No window animations or rounded window corners.** surfd puts the polish
  where Sway allows it: a rounded floating bar with transitions, rounded
  notifications/launcher/lock screen, consistent GTK/Qt colours, a themed boot
  and login. [SwayFX](https://github.com/WillPower3309/swayfx), a drop-in
  Sway fork with rounded corners, blur and shadows, is on the roadmap as an
  optional session.
- **Tiling can intimidate newcomers.** surfd adds a floating, mouse-first
  mode (`surfctl mode floating`), a task list bar preset, touchpad gestures
  and the **Super + /** cheat sheet.
