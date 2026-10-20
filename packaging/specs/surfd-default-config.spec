# surfd-default-config — the surfd session, login screen and defaults
Name:           surfd-default-config
Version:        0.1.0
Release:        1%{?dist}
Summary:        Default configuration and session for the surfd desktop
License:        MIT
URL:            https://github.com/advay-saha/surfd
Source0:        surfd-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3
BuildRequires:  python3-tomlkit
BuildRequires:  systemd-rpm-macros

# Installing this package on any Fedora gives you the surfd desktop.
Requires:       surfctl = %{version}-%{release}
Requires:       surfd-theme = %{version}-%{release}
# Any sway-config-* provider works: surfctl generates the real config.
Requires:       sway
Requires:       swaybg
Requires:       swaylock
Requires:       swayidle
Requires:       waybar
Requires:       fuzzel
Requires:       mako
Requires:       foot
Requires:       grim
Requires:       slurp
Requires:       wl-clipboard
Requires:       brightnessctl
Requires:       playerctl
Requires:       wireplumber
Requires:       lxpolkit
Requires:       xdg-desktop-portal-wlr
Requires:       xdg-desktop-portal-gtk
Requires:       qt6ct
Requires:       greetd
Requires:       greetd-selinux
Requires:       gtkgreet
Requires:       NetworkManager
Requires:       flatpak
Requires:       /usr/bin/gdbus
Requires:       /usr/bin/gsettings
Requires(post): systemd

%description
Everything that makes a Sway install into the surfd desktop: the default
surfd.toml, the surfd-session launcher (with a safe fallback when the
configuration is broken), helper scripts, the greetd login screen, the
Flathub first-boot service and the systemd user session target.

%package -n surfd-live
Summary:        Live-media session setup for surfd
Requires:       %{name} = %{version}-%{release}
Requires:       sudo

%description -n surfd-live
Creates a password-less live user with automatic login when booted from
surfd live media (kernel option rd.live.image). Anaconda removes this
package from installed systems.

%prep
%autosetup -n surfd-%{version}

%build
# Login screen style generated from the default theme by the same code
# surfctl uses, so it always matches the desktop.
mkdir -p build/sys/defaults
cp config/defaults/surfd.toml build/sys/defaults/
ln -sfn ../../theme/themes build/sys/themes
SURFD_SYSTEM_DIR=$PWD/build/sys HOME=$PWD/build/home PYTHONPATH=src/surfctl %{__python3} -c '
from surfd import generate
ctx = generate.build_context()
print(generate.greeter_css(ctx, "%{_datadir}/surfd/greeter/background"), end="")
' > build/greeter-style.css

%install
# defaults and fallback
install -Dpm 0644 config/defaults/surfd.toml %{buildroot}%{_datadir}/surfd/defaults/surfd.toml
install -Dpm 0644 config/fallback/sway.conf %{buildroot}%{_datadir}/surfd/fallback/sway.conf

# session
install -Dpm 0755 src/session/surfd-session %{buildroot}%{_bindir}/surfd-session
install -Dpm 0644 docs/man/surfd-session.1 %{buildroot}%{_mandir}/man1/surfd-session.1
install -d %{buildroot}%{_libexecdir}/surfd
install -pm 0755 src/session/libexec/surfd-bar src/session/libexec/surfd-idle \
    src/session/libexec/surfd-dynwall src/session/libexec/surfd-greeter %{buildroot}%{_libexecdir}/surfd/
install -Dpm 0644 src/session/surfd.desktop %{buildroot}%{_datadir}/wayland-sessions/surfd.desktop
install -Dpm 0644 config/systemd/surfd-session.target %{buildroot}%{_userunitdir}/surfd-session.target
install -d %{buildroot}%{_sysconfdir}/surfd/sway.d

# login screen
install -Dpm 0644 config/greetd/config.toml %{buildroot}%{_datadir}/surfd/greetd/config.toml
install -Dpm 0644 config/greetd/config.toml %{buildroot}%{_sysconfdir}/surfd/greetd/config.toml
install -Dpm 0644 config/greetd/sway-config %{buildroot}%{_sysconfdir}/surfd/greetd/sway-config
install -Dpm 0644 build/greeter-style.css %{buildroot}%{_sysconfdir}/surfd/greetd/style.css
install -d %{buildroot}%{_sysconfdir}/surfd/greetd/sway.d
install -Dpm 0644 config/systemd/greetd-surfd.conf %{buildroot}%{_unitdir}/greetd.service.d/surfd.conf
install -Dpm 0644 config/systemd/surfd-greeter.sysusers %{buildroot}%{_sysusersdir}/surfd-greeter.conf
install -Dpm 0644 config/systemd/surfd-greeter.tmpfiles %{buildroot}%{_tmpfilesdir}/surfd-greeter.conf
install -d %{buildroot}%{_localstatedir}/lib/surfd-greeter

# flathub on first boot
install -Dpm 0644 config/systemd/surfd-flathub.service %{buildroot}%{_unitdir}/surfd-flathub.service

# live media
install -Dpm 0755 config/live/surfd-livesys %{buildroot}%{_libexecdir}/surfd/surfd-livesys
install -Dpm 0644 config/live/surfd-livesys.service %{buildroot}%{_unitdir}/surfd-livesys.service
install -Dpm 0644 config/live/90-surfd-live-cleanup.ks \
    %{buildroot}%{_datadir}/anaconda/post-scripts/90-surfd-live-cleanup.ks

%check
grep -q 'box#body' %{buildroot}%{_sysconfdir}/surfd/greetd/style.css
bash -n %{buildroot}%{_bindir}/surfd-session
for f in %{buildroot}%{_libexecdir}/surfd/*; do bash -n "$f"; done

%post
%systemd_post surfd-flathub.service
%tmpfiles_create %{_tmpfilesdir}/surfd-greeter.conf

%preun
%systemd_preun surfd-flathub.service

%postun
%systemd_postun surfd-flathub.service

%post -n surfd-live
%systemd_post surfd-livesys.service

%preun -n surfd-live
%systemd_preun surfd-livesys.service

%files
%license LICENSE
%doc README.md
%{_mandir}/man1/surfd-session.1*
%dir %{_datadir}/surfd
%{_datadir}/surfd/defaults
%{_datadir}/surfd/fallback
%{_datadir}/surfd/greetd
%{_bindir}/surfd-session
%dir %{_libexecdir}/surfd
%{_libexecdir}/surfd/surfd-bar
%{_libexecdir}/surfd/surfd-idle
%{_libexecdir}/surfd/surfd-dynwall
%{_libexecdir}/surfd/surfd-greeter
%{_datadir}/wayland-sessions/surfd.desktop
%{_userunitdir}/surfd-session.target
%dir %{_sysconfdir}/surfd
%dir %{_sysconfdir}/surfd/sway.d
%dir %{_sysconfdir}/surfd/greetd
%dir %{_sysconfdir}/surfd/greetd/sway.d
%config(noreplace) %{_sysconfdir}/surfd/greetd/config.toml
%config(noreplace) %{_sysconfdir}/surfd/greetd/sway-config
%config(noreplace) %{_sysconfdir}/surfd/greetd/style.css
%dir %{_unitdir}/greetd.service.d
%{_unitdir}/greetd.service.d/surfd.conf
%{_unitdir}/surfd-flathub.service
%{_sysusersdir}/surfd-greeter.conf
%{_tmpfilesdir}/surfd-greeter.conf
%dir %attr(0750,surfd-greeter,surfd-greeter) %{_localstatedir}/lib/surfd-greeter

%files -n surfd-live
%{_libexecdir}/surfd/surfd-livesys
%{_unitdir}/surfd-livesys.service
%dir %{_datadir}/anaconda
%dir %{_datadir}/anaconda/post-scripts
%{_datadir}/anaconda/post-scripts/90-surfd-live-cleanup.ks

%changelog
* Mon Oct 19 2026 surfd contributors <surfd@example.invalid> - 0.1.0-1
- Initial release
