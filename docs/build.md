# Building surfd

Everything is driven by `build.sh`. ISO builds must run on Fedora (a VM, a
real machine, or a privileged Fedora container) matching the target release.

```
./build.sh [options] rpms | check | ks | iso | netinstall | container
```

| Command | What it does | Needs |
|---|---|---|
| `rpms` | builds every spec in `packaging/specs` into `out/repo` (+ repodata); `%check` runs the test suite | `rpm-build createrepo_c` + BuildRequires |
| `check` | confirms every package and group in the kickstarts exists for the target release/arch | Fedora, network |
| `ks` | writes the flattened kickstart to `out/` (inspect what will be installed) | `pykickstart` |
| `iso` | `rpms`, then a live ISO with `livemedia-creator --no-virt`, then SHA256 and a size check | Fedora, root |
| `netinstall` | embeds an install kickstart into a Fedora netinstall ISO with `mkksiso` | a hosted surfd repo (`--repo-url`) |
| `container` | experimental bootc image (see `containers/README.md`) | `podman` |

Options: `--releasever N` (default 44), `--out DIR`, `--repo-url URL` (use a
hosted surfd repo such as Copr instead of local RPMs), `--skip-rpms`,
`--selinux-permissive`, `--keep-build`, `--dry-run`.

## Live ISO, step by step (Fedora 44 host)

```sh
sudo dnf install lorax lorax-lmc-novirt anaconda-tui pykickstart rpm-build createrepo_c \
  python3-pytest python3-tomlkit python3-pillow librsvg2-tools desktop-file-utils appstream \
  systemd-rpm-macros
git clone https://github.com/advay-saha/surfd && cd surfd
./build.sh rpms                              # ~1 min
./build.sh check                             # ~1 min, catches renamed packages
sudo ./build.sh --skip-rpms --selinux-permissive iso    # 20-60 min
ls -lh out/iso/                              # surfd-0.1.0-f44-x86_64.iso + .sha256
```

`livemedia-creator --no-virt` installs into a directory on the build host with
Anaconda, which requires SELinux to be permissive *on the build host* while it
runs. `--selinux-permissive` switches it and restores it afterwards. The image
itself is built with `selinux --enforcing` and boots enforcing.

The kickstarts disable weak dependencies (`%packages --exclude-weakdeps`, the
kickstart form of `--setopt=install_weak_deps=False`).

### In a container instead of a VM

```sh
sudo podman run --rm -it --privileged -v /dev:/dev -v "$PWD":/src -w /src \
  registry.fedoraproject.org/fedora:44 bash
# inside: install the packages above, then
./build.sh rpms && ./build.sh --skip-rpms iso
```

This is exactly what `.github/workflows/iso.yml` does.

### aarch64

Run the same commands on an aarch64 Fedora machine (or GitHub's
`ubuntu-24.04-arm` runners, which the release workflow uses). There is no
cross-building; `build.sh` picks `kickstarts/surfd-$(uname -m).ks`.

### Moving to Fedora 45

Fedora 45 is due on 27 October 2026. Build against it with
`--releasever 45` on a Fedora 45 host; run `./build.sh --releasever 45 check`
first. The kickstarts already validate with the F45 syntax.

## Kickstart structure

```
surfd-x86_64.ks / surfd-aarch64.ks   entry points (build.sh picks one)
 ├─ surfd.ks                          composition
 │   ├─ surfd-repos.ks                Fedora + updates ($releasever/$basearch)
 │   ├─ surfd-base.ks                 locale, SELinux, firewall, services, kernel, firmware, system tools
 │   ├─ surfd-desktop.ks              Sway session, theme, apps, surfd components
 │   └─ surfd-live.ks                 live-only: disk layout, Anaconda, dracut-live, surfd-live
 └─ surfd-boot-<arch>.ks              shim/GRUB (UEFI + BIOS on x86_64), microcode
```

`build.sh` flattens this with `ksflatten` and prepends the surfd package
repository (`file://out/repo`, or `--repo-url`). The netinstall flavour uses
the same files without `surfd-live.ks`, so Anaconda asks for a disk and
installs a real bootloader.

## RPM packages

| Spec | Binary packages | Contents |
|---|---|---|
| `surfd-release` | surfd-release | os-release (ID=surfd, ID_LIKE=fedora), systemd presets, dist macros, dnf weak-deps policy, surfd.repo (disabled) |
| `surfd-theme` | surfd-theme, plymouth-theme-surfd, surfd-logos | theme packs + rendered wallpapers, boot splash, logos, Anaconda profile & art |
| `surfd-default-config` | surfd-default-config, surfd-live | defaults, surfd-session, greetd login screen, systemd units; live-user setup |
| `surfctl` | surfctl, surfd-hwprobe | the Python package/CLI; hardware probe |
| `surfd-settings` | surfd-settings | Surf Settings and Welcome |

All sources come from one tarball of this repository, created by
`packaging/build-rpms.sh`. On a non-Fedora host, `make rpm-test` builds with
`--nodeps` and test macros, which is how the specs are checked in CI without
Fedora mirrors.

## Copr (hosted repository)

1. Create a Copr project (e.g. `you/surfd`) for `fedora-44-x86_64` and
   `fedora-44-aarch64`.
2. Add a package per spec with source type **Custom** (`make srpm`) or **SCM**
   using `.copr/Makefile` from this repository:
   `make -f .copr/Makefile srpm outdir=<dir> spec=packaging/specs/<name>.spec`.
3. Set `%global copr_project you/surfd` in `surfd-release.spec`; installed
   systems then have `/etc/yum.repos.d/surfd.repo` ready
   (`sudo dnf config-manager setopt surfd.enabled=1`).
4. Build ISOs from it with `./build.sh --repo-url https://download.copr.fedorainfracloud.org/results/you/surfd/fedora-44-$(uname -m)/ iso`.

## Local repository workflow

```sh
./build.sh rpms                          # out/repo with repodata
sudo dnf --repofrompath=surfd,file://$PWD/out/repo --setopt=surfd.gpgcheck=0 \
  install surfd-default-config surfd-settings
```

## Checking size

```sh
sudo tools/iso-size-report.sh out/iso/surfd-*.iso   # 40 largest packages inside the image
```

The budget is 1.5 GiB; `build.sh` warns when an ISO exceeds it.
