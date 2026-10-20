# surfd-settings — Surf Settings and the first-login Welcome app
Name:           surfd-settings
Version:        0.1.0
Release:        1%{?dist}
Summary:        Settings and welcome apps for the surfd desktop
License:        MIT AND CC-BY-SA-4.0
URL:            https://github.com/advay-saha/surfd
Source0:        surfd-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3
# python3-devel brings the Python RPM macros (python3_sitelib and friends)
BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
BuildRequires:  python3-pytest

Requires:       surfctl = %{version}-%{release}
Requires:       python3-gobject
Requires:       typelib(Gtk) = 4.0
Requires:       typelib(Adw) = 1
Recommends:     surfd-hwprobe
Recommends:     polkit

%description
Surf Settings is a small GTK 4 and libadwaita app that edits surfd.toml:
theme, accent color, wallpaper, fonts, window layout, bar, key bindings and
default apps. surfd Welcome is the first-login tour: pick a look, learn the
essential keys, and (on live media) start the installer.

%package -n surfd-installer
Summary:        Simple installer for surfd live media
Requires:       python3-gobject
Requires:       typelib(Gtk) = 4.0
Requires:       typelib(Adw) = 1
# the install engine
Requires:       gdisk
Requires:       util-linux
Requires:       e2fsprogs
Requires:       btrfs-progs
Requires:       dosfstools
Requires:       cryptsetup
Requires:       rsync
Requires:       efibootmgr
Requires:       grub2-tools
Requires:       policycoreutils
Requires:       systemd
Requires:       sudo
Recommends:     polkit

%description -n surfd-installer
Surf Installer installs surfd from the live system onto a whole disk in five
screens: language and keyboard, disk (with optional encryption), account,
review, done. Dual boot and custom partitioning stay with Fedora's full
installer, which it can open. The installed system does not keep this package.

%prep
%autosetup -n surfd-%{version}

%build
# Pure Python; nothing to build.

%install
install -d %{buildroot}%{python3_sitelib}
cp -a src/settings/surf_settings %{buildroot}%{python3_sitelib}/
find %{buildroot}%{python3_sitelib}/surf_settings -name '__pycache__' -prune -exec rm -rf {} +
install -Dpm 0755 src/settings/bin/surf-settings %{buildroot}%{_bindir}/surf-settings
install -Dpm 0755 src/settings/bin/surf-welcome %{buildroot}%{_bindir}/surf-welcome
sed -i '1s|^#!.*|#!%{__python3} -sP|' %{buildroot}%{_bindir}/surf-settings %{buildroot}%{_bindir}/surf-welcome
install -Dpm 0644 -t %{buildroot}%{_datadir}/applications \
    src/settings/data/org.surfd.Settings.desktop src/settings/data/org.surfd.Welcome.desktop
install -Dpm 0644 src/settings/data/org.surfd.Settings.metainfo.xml \
    %{buildroot}%{_metainfodir}/org.surfd.Settings.metainfo.xml
install -Dpm 0644 -t %{buildroot}%{_datadir}/icons/hicolor/scalable/apps \
    src/settings/data/org.surfd.Settings.svg src/settings/data/org.surfd.Welcome.svg

# installer
cp -a src/installer/surf_installer %{buildroot}%{python3_sitelib}/
find %{buildroot}%{python3_sitelib}/surf_installer -name '__pycache__' -prune -exec rm -rf {} +
install -Dpm 0755 src/installer/bin/surf-installer %{buildroot}%{_bindir}/surf-installer
install -Dpm 0755 src/installer/bin/surf-installer-engine %{buildroot}%{_libexecdir}/surfd/surf-installer-engine
sed -i '1s|^#!.*|#!%{__python3} -sP|' %{buildroot}%{_bindir}/surf-installer %{buildroot}%{_libexecdir}/surfd/surf-installer-engine
install -Dpm 0644 src/installer/data/org.surfd.Installer.desktop %{buildroot}%{_datadir}/applications/org.surfd.Installer.desktop
install -Dpm 0644 src/installer/data/org.surfd.Installer.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/org.surfd.Installer.svg

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/*.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/org.surfd.Settings.metainfo.xml
%{__python3} -m py_compile %{buildroot}%{python3_sitelib}/surf_settings/*.py %{buildroot}%{python3_sitelib}/surf_installer/*.py
# installer plan checks, generated files and the dry-run command sequence
# (the loop-device tests skip themselves when not run as root)
PYTHONDONTWRITEBYTECODE=1 %{__python3} -m pytest -q -p no:cacheprovider src/installer/tests

%files
%license LICENSE LICENSES/CC-BY-SA-4.0.txt
%doc README.md
%{_bindir}/surf-settings
%{_bindir}/surf-welcome
%{python3_sitelib}/surf_settings
%{_datadir}/applications/org.surfd.Settings.desktop
%{_datadir}/applications/org.surfd.Welcome.desktop
%{_metainfodir}/org.surfd.Settings.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/org.surfd.Settings.svg
%{_datadir}/icons/hicolor/scalable/apps/org.surfd.Welcome.svg

%files -n surfd-installer
%license LICENSE
%doc docs/installer.md
%{_bindir}/surf-installer
%dir %{_libexecdir}/surfd
%{_libexecdir}/surfd/surf-installer-engine
%{python3_sitelib}/surf_installer
%{_datadir}/applications/org.surfd.Installer.desktop
%{_datadir}/icons/hicolor/scalable/apps/org.surfd.Installer.svg

%changelog
* Mon Oct 19 2026 surfd contributors <surfd@example.invalid> - 0.1.0-1
- Initial release
