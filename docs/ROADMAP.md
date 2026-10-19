# Roadmap

Honest next steps, roughly in order. Nothing here exists yet.

## Before a first public release (0.1.x)

- **Boot-test the ISO** on x86_64 and aarch64 in QEMU and on at least three
  laptops (Intel, AMD, NVIDIA hybrid) using the [testing checklist](testing.md).
  Fix whatever the first real boot finds — this has not happened yet.
- **Confirm package names on Fedora 44** with `./build.sh check` (CI runs it;
  the names could not be checked against the Fedora mirrors while writing).
- **Measure the budgets**: idle RAM (< 400 MB) on an installed system and ISO
  size (< 1.5 GiB); trim the package set with `tools/iso-size-report.sh`.
- **Greeter under SELinux enforcing**: verify greetd + gtkgreet in Sway with
  `greetd-selinux`; write a small policy module if anything is denied.
- **Anaconda branding**: confirm the GTK installer picks up
  `/etc/anaconda/profile.d/surfd.conf` and the stylesheet on a live install.
- **Preset policy**: compare `systemctl list-unit-files --state=enabled` with
  a stock Fedora install and adjust `release/presets/` (they replace
  `fedora-release-common`'s presets).
- **Full CC BY-SA 4.0 legal text** in `LICENSES/CC-BY-SA-4.0.txt` (currently a summary + link).

## Distribution

- **Hosted repository**: a Copr project (`.copr/Makefile` is ready) so
  installed systems get surfd updates through `dnf`; enable `surfd.repo` in
  `surfd-release`. Later, a signed repository on our own infrastructure.
- **Secure Boot signing via shim**: surfd ships Fedora's signed shim, GRUB and
  kernel, so Secure Boot already works with no surfd-specific binaries. A
  surfd-owned shim would only be needed if surfd ever ships its own kernel or
  bootloader; that requires a shim review submission
  (rhboot/shim-review) and an EV code-signing certificate — out of scope until
  then. Shorter-term: document and automate MOK enrollment for akmods
  (NVIDIA, wl) in Surf Settings.
- **Published ISOs** with GPG-signed SHA256SUMS (the workflow already
  publishes plain checksums).
- **Fedora 45** (due 27 October 2026): build with `--releasever 45`, then make
  it the default once released and tested.

## Arm

- **Raspberry Pi 4/5 image**: an `.raw.xz` disk image built with
  `image-builder`/`kiwi` from the same package set, plus Pi firmware.
- Boot-test on a Snapdragon X laptop as Fedora's support matures.

## Immutable variant

- Move the bootc image (`containers/`) from experimental to supported:
  build it in CI, publish to a registry, produce ISOs/qcow2 with
  `bootc-image-builder`, and document `bootc switch`/`bootc upgrade`/rollback.
- Make surfctl fully home-directory based (already true) and test it on the
  read-only `/usr` of bootc.

## Desktop

- **SwayFX as an optional session** (rounded corners, blur, shadows) selected
  by a `surfd.toml` setting, if it is packaged in Fedora.
- Per-output settings in `surfd.toml` (resolution, position, scale) and
  kanshi profiles for docking.
- Night light (`wlsunset`) and a clipboard history (`cliphist`) as opt-in settings.
- Accessibility: Orca screen reader testing, high-contrast theme pack,
  larger-text preset.
- Translations for Surf Settings and Welcome (gettext).
- Hot-reloading foot colours (`foot` signals) so terminals change instantly.
- Switch `surfctl`/`surfd-settings` packaging to the pyproject RPM macros for
  a Fedora package review.
- A small theme gallery website fed by exported theme packs.
