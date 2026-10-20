# surfd-theme — theme packs, wallpapers, boot splash and logos
Name:           surfd-theme
Version:        0.1.0
Release:        1%{?dist}
Summary:        Theme packs and wallpapers for the surfd desktop
# Artwork CC-BY-SA-4.0; the small render tooling is MIT.
License:        CC-BY-SA-4.0 AND MIT
URL:            https://github.com/advay-saha/surfd
Source0:        surfd-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3
BuildRequires:  python3-pillow
BuildRequires:  librsvg2-tools

Requires:       adw-gtk3-theme
Requires:       papirus-icon-theme
Requires:       breeze-cursor-theme
Requires:       rsms-inter-fonts
Requires:       jetbrains-mono-fonts

%description
The theme packs that ship with surfd (Tide, Driftwood and Kelp, each with
dark and light variants) and their original wallpapers, plus surfd's own
gradient wallpapers (Tide, Driftwood, Kelp and Dusk; dark and light; 16:9,
16:10 and ultra-wide sizes). Theme packs are plain folders; the included
theme-making guide explains the format.

%package -n surfd-wallpapers
Summary:        Dynamic (time-of-day) and still wallpapers by other artists for surfd
# Artwork by other people, shipped at the maintainer's decision; licences NOT verified (see CREDITS.md).
License:        LicenseRef-third-party-unverified
Requires:       surfd-default-config

%description -n surfd-wallpapers
Eight wallpapers that change through the day (`[wallpaper] dynamic` in
surfd.toml), including the default, "Low-poly mountain", 18 still wallpapers
for the Picture gallery in Surf Settings, and a theme with colors picked from
each of them. The wallpapers are other people's artwork; credits, sources and
license status:
/usr/share/doc/surfd-wallpapers/CREDITS.md.

%package -n plymouth-theme-surfd
Summary:        surfd boot splash
License:        CC-BY-SA-4.0
Requires:       plymouth-plugin-two-step
Requires:       plymouth-scripts

%description -n plymouth-theme-surfd
The surfd Plymouth boot splash: the S logo on deep ocean navy with a
seafoam spinner. Activate with: sudo plymouth-set-default-theme -R surfd

%package -n surfd-logos
Summary:        surfd logos and installer branding
License:        CC-BY-SA-4.0
Requires:       generic-logos
Conflicts:      fedora-logos

%description -n surfd-logos
surfd logos (the S mark and wordmark) and the Anaconda installer profile and
artwork. Fedora logos are not included, as required for Fedora Remixes;
generic-logos covers the system logo paths.

%prep
%autosetup -n surfd-%{version}

%build
%{__python3} theme/tools/render.py build/art

%install
# theme packs: surfd's own (surfd-theme) and one per wallpaper (surfd-wallpapers, with the pictures)
install -d %{buildroot}%{_datadir}/surfd/themes
cp -a build/art/themes/. %{buildroot}%{_datadir}/surfd/themes/
cp -a wallpapers/third-party/themes/. %{buildroot}%{_datadir}/surfd/themes/
find %{buildroot}%{_datadir}/surfd/themes -type d -exec chmod 0755 {} +
find %{buildroot}%{_datadir}/surfd/themes -type f -exec chmod 0644 {} +
for t in wallpapers/third-party/themes/*/; do
  echo "%{_datadir}/surfd/themes/$(basename "$t")"
done > wallpaper-themes.list
# default login background is the Tide (dark) colourway
install -d %{buildroot}%{_datadir}/surfd/greeter
ln -s ../wallpapers/surfd/tide/tide-dark-3840x2160.jpg %{buildroot}%{_datadir}/surfd/greeter/background

# surfd's own gradient wallpapers (surfd-theme), one folder per colourway, every size
for c in tide driftwood kelp dusk; do
  install -d %{buildroot}%{_datadir}/surfd/wallpapers/surfd/$c
  install -pm 0644 wallpapers/generated/$c/*.jpg %{buildroot}%{_datadir}/surfd/wallpapers/surfd/$c/
done
# other artists' wallpapers (surfd-wallpapers): every dynamic set and the still images
install -d %{buildroot}%{_datadir}/surfd/wallpapers/dynamic %{buildroot}%{_datadir}/surfd/wallpapers/static
cp -a wallpapers/third-party/dynamic/. %{buildroot}%{_datadir}/surfd/wallpapers/dynamic/
install -pm 0644 wallpapers/third-party/static/* %{buildroot}%{_datadir}/surfd/wallpapers/static/
find %{buildroot}%{_datadir}/surfd/wallpapers -type d -exec chmod 0755 {} +
find %{buildroot}%{_datadir}/surfd/wallpapers -type f -exec chmod 0644 {} +
# some dynamic sets reuse one picture for two frames: hard-link those instead of shipping copies
(cd %{buildroot}%{_datadir}/surfd/wallpapers/dynamic &&
 find . -type f -name '*.jpg' -exec md5sum {} + | sort |
 awk '$1 == sum { print keep, $2; next } { sum = $1; keep = $2 }' |
 while read -r keep dup; do ln -f "$keep" "$dup"; done)

# plymouth
install -d %{buildroot}%{_datadir}/plymouth/themes/surfd
install -pm 0644 build/art/plymouth/surfd/* %{buildroot}%{_datadir}/plymouth/themes/surfd/

# logos
install -d %{buildroot}%{_datadir}/surfd/logos
install -pm 0644 theme/logos/*.svg build/art/logos/surfd-logo*.png %{buildroot}%{_datadir}/surfd/logos/
# os-release LOGO=surfd-logo resolves through the icon theme
install -Dpm 0644 theme/logos/surfd-mark.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/surfd-logo.svg
rm %{buildroot}%{_datadir}/surfd/logos/surfd-mark.svg
ln -s ../../icons/hicolor/scalable/apps/surfd-logo.svg %{buildroot}%{_datadir}/surfd/logos/surfd-mark.svg
for s in 64 128 256 512; do
  install -Dpm 0644 build/art/logos/surfd-mark-$s.png \
    %{buildroot}%{_datadir}/icons/hicolor/${s}x${s}/apps/surfd-logo.png
done

# anaconda branding
install -Dpm 0644 theme/anaconda/surfd.conf %{buildroot}%{_sysconfdir}/anaconda/profile.d/surfd.conf
install -d %{buildroot}%{_datadir}/anaconda/pixmaps/surfd
install -pm 0644 theme/anaconda/surfd.css build/art/anaconda/*.png %{buildroot}%{_datadir}/anaconda/pixmaps/surfd/

%check
# every theme's wallpaper is installed: a gallery picture by name, or a dynamic set
w=%{buildroot}%{_datadir}/surfd/wallpapers
test -n "$(ls $w/surfd/tide/tide-dark-3840x2160.jpg)" && test -e %{buildroot}%{_datadir}/surfd/greeter/background
for t in %{buildroot}%{_datadir}/surfd/themes/*/theme.toml; do
  for pic in $(sed -n 's/^wallpaper *= *"\([^"/]*\)".*/\1/p' $t); do
    ls $w/surfd/*/$pic.* $w/static/$pic.* 2>/dev/null | grep -q . || { echo "$t: no picture $pic"; exit 1; }
  done
  for set in $(sed -n 's/^dynamic *= *"\(.*\)".*/\1/p' $t); do test -f $w/dynamic/$set/wallpaper.toml; done
done
test $(ls -d %{buildroot}%{_datadir}/surfd/themes/*/ | wc -l) -ge 30
test $(ls %{buildroot}%{_datadir}/plymouth/themes/surfd/throbber-*.png | wc -l) -eq 36
# every dynamic set is complete (every frame named in wallpaper.toml exists), the default among them
test -f %{buildroot}%{_datadir}/surfd/wallpapers/dynamic/low-poly-mountain/wallpaper.toml
for set in %{buildroot}%{_datadir}/surfd/wallpapers/dynamic/*/; do
  test -f $set/wallpaper.toml
  for f in $(sed -n 's/^\(file\|light\|dark\) *= *"\(.*\)"/\2/p' $set/wallpaper.toml); do test -f $set/$f; done
done
# four gradient colourways x dark/light x four sizes, and the still images
test $(ls %{buildroot}%{_datadir}/surfd/wallpapers/surfd/*/*.jpg | wc -l) -eq 32
test $(ls %{buildroot}%{_datadir}/surfd/wallpapers/static | wc -l) -ge 18

%files
%license LICENSES/CC-BY-SA-4.0.txt LICENSES/MIT.txt
%doc docs/theme-making.md
%dir %{_datadir}/surfd
%dir %{_datadir}/surfd/themes
%{_datadir}/surfd/themes/tide
%{_datadir}/surfd/themes/driftwood
%{_datadir}/surfd/themes/kelp
%{_datadir}/surfd/themes/dusk
%{_datadir}/surfd/greeter
%dir %{_datadir}/surfd/wallpapers
%{_datadir}/surfd/wallpapers/surfd

%files -n surfd-wallpapers -f wallpaper-themes.list
%license LICENSES/LicenseRef-third-party-unverified.txt
%doc wallpapers/third-party/CREDITS.md docs/dynamic-wallpapers.md
%dir %{_datadir}/surfd
%dir %{_datadir}/surfd/themes
%dir %{_datadir}/surfd/wallpapers
%{_datadir}/surfd/wallpapers/dynamic
%{_datadir}/surfd/wallpapers/static

%files -n plymouth-theme-surfd
%license LICENSES/CC-BY-SA-4.0.txt
%{_datadir}/plymouth/themes/surfd

%files -n surfd-logos
%license LICENSES/CC-BY-SA-4.0.txt
%dir %{_datadir}/surfd
%{_datadir}/surfd/logos
%{_datadir}/icons/hicolor/scalable/apps/surfd-logo.svg
%{_datadir}/icons/hicolor/*x*/apps/surfd-logo.png
%dir %{_sysconfdir}/anaconda
%dir %{_sysconfdir}/anaconda/profile.d
%config(noreplace) %{_sysconfdir}/anaconda/profile.d/surfd.conf
%dir %{_datadir}/anaconda
%dir %{_datadir}/anaconda/pixmaps
%{_datadir}/anaconda/pixmaps/surfd

%changelog
* Mon Oct 19 2026 surfd contributors <surfd@example.invalid> - 0.1.0-1
- Initial release
