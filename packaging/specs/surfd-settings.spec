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
BuildRequires:  desktop-file-utils
BuildRequires:  appstream

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

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/*.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/org.surfd.Settings.metainfo.xml
%{__python3} -m py_compile %{buildroot}%{python3_sitelib}/surf_settings/*.py

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

%changelog
* Mon Oct 19 2026 surfd contributors <surfd@example.invalid> - 0.1.0-1
- Initial release
