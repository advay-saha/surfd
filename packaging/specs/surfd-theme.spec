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
dark and light variants) and their original wallpapers. Theme packs are
plain folders; the included theme-making guide explains the format.

%package -n surfd-wallpapers
Summary:        Dynamic (time-of-day) wallpapers for surfd
# Artwork by other people whose licence has NOT been verified: replace or confirm before a release.
License:        LicenseRef-third-party-unverified
Requires:       surfd-default-config

%description -n surfd-wallpapers
Wallpapers that change through the day, used by `[wallpaper] dynamic` in surfd.toml. Includes the
default, "Low-poly mountain". Credits and licence status: /usr/share/doc/surfd-wallpapers/CREDITS.md.

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
# theme packs + rendered wallpapers
install -d %{buildroot}%{_datadir}/surfd/themes
cp -a build/art/themes/. %{buildroot}%{_datadir}/surfd/themes/
find %{buildroot}%{_datadir}/surfd/themes -type f -exec chmod 0644 {} +
# default login background is the Tide (dark) wallpaper
install -d %{buildroot}%{_datadir}/surfd/greeter
ln -s ../themes/tide/wallpapers/tide-dark.jpg %{buildroot}%{_datadir}/surfd/greeter/background

# dynamic wallpapers (only the default set is packaged)
install -d %{buildroot}%{_datadir}/surfd/wallpapers/dynamic
cp -a wallpapers/third-party/dynamic/low-poly-mountain %{buildroot}%{_datadir}/surfd/wallpapers/dynamic/
find %{buildroot}%{_datadir}/surfd/wallpapers -type f -exec chmod 0644 {} +

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
# every theme has both variants and a rendered wallpaper for each
for t in %{buildroot}%{_datadir}/surfd/themes/*/; do
  for v in dark light; do
    ls "$t"wallpapers/*-$v.jpg >/dev/null
  done
done
test $(ls %{buildroot}%{_datadir}/plymouth/themes/surfd/throbber-*.png | wc -l) -eq 36
# the default dynamic wallpaper is complete: every frame named in wallpaper.toml exists
set=%{buildroot}%{_datadir}/surfd/wallpapers/dynamic/low-poly-mountain
test -f $set/wallpaper.toml
for f in $(sed -n 's/^\(file\|light\|dark\) *= *"\(.*\)"/\2/p' $set/wallpaper.toml); do test -f $set/$f; done

%files
%license LICENSES/CC-BY-SA-4.0.txt LICENSES/MIT.txt
%doc docs/theme-making.md
%dir %{_datadir}/surfd
%{_datadir}/surfd/themes
%{_datadir}/surfd/greeter

%files -n surfd-wallpapers
%license LICENSES/LicenseRef-third-party-unverified.txt
%doc wallpapers/third-party/CREDITS.md docs/dynamic-wallpapers.md
%dir %{_datadir}/surfd
%dir %{_datadir}/surfd/wallpapers
%{_datadir}/surfd/wallpapers/dynamic

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
