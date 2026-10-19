# surfd-release — identity of the surfd Fedora Remix (replaces fedora-release)
%global surfd_version 0.1.0
%global surfd_url https://github.com/surfd/surfd
%global copr_project surfd/surfd
%global fedora_ver %{?fedora}%{!?fedora:44}

Name:           surfd-release
Version:        %{fedora_ver}
Release:        1%{?dist}
Summary:        surfd release files (os-release, presets, repositories)
License:        MIT
URL:            %{surfd_url}
Source0:        surfd-%{surfd_version}.tar.gz
BuildArch:      noarch

# What fedora-release provides, so Fedora packages and dnf work unchanged.
Provides:       system-release = %{version}-%{release}
Provides:       system-release(%{version}) = %{version}-%{release}
Provides:       system-release(releasever) = %{version}
Provides:       base-module(platform:f%{version}) = %{version}-%{release}
Conflicts:      fedora-release-common
Conflicts:      generic-release-common
Requires:       fedora-repos(%{version})

%description
Release files for surfd, a lightweight Sway-based Fedora Remix: os-release,
the systemd preset policy, RPM dist macros, the dnf weak-dependency policy and
the (disabled until published) surfd package repository.

surfd is based on Fedora Linux but is not an official Fedora project and is
not endorsed by the Fedora Project.

%prep
%autosetup -n surfd-%{surfd_version}

%build
sed -e 's|@FEDORA@|%{version}|g' -e 's|@SURFD_VERSION@|%{surfd_version}|g' -e 's|@URL@|%{surfd_url}|g' \
    release/os-release.in > os-release
sed -e 's|@FEDORA@|%{version}|g' -e 's|@SURFD_MAJOR_MINOR@|%(echo %{surfd_version} | cut -d. -f1,2)|g' \
    release/macros.dist.in > macros.dist
sed -e 's|@COPR@|%{copr_project}|g' release/surfd.repo > surfd.repo
echo "surfd release %{surfd_version} (based on Fedora Linux %{version})" > surfd-release
echo "cpe:/o:surfd:surfd:%{version}" > system-release-cpe

%install
install -Dpm 0644 os-release %{buildroot}%{_prefix}/lib/os-release
install -d %{buildroot}%{_sysconfdir}
ln -s ../usr/lib/os-release %{buildroot}%{_sysconfdir}/os-release
install -pm 0644 surfd-release %{buildroot}%{_sysconfdir}/surfd-release
ln -s surfd-release %{buildroot}%{_sysconfdir}/system-release
ln -s surfd-release %{buildroot}%{_sysconfdir}/redhat-release
install -pm 0644 system-release-cpe %{buildroot}%{_sysconfdir}/system-release-cpe
printf '\\S\nKernel \\r on \\m (\\l)\n\n' > %{buildroot}%{_sysconfdir}/issue
printf '\\S\nKernel \\r on \\m (\\l)\n\n' > %{buildroot}%{_sysconfdir}/issue.net

install -Dpm 0644 -t %{buildroot}%{_presetdir} release/presets/*.preset
install -Dpm 0644 -t %{buildroot}%{_userpresetdir} release/user-presets/*.preset
install -Dpm 0644 macros.dist %{buildroot}%{_rpmmacrodir}/macros.dist
install -Dpm 0644 surfd.repo %{buildroot}%{_sysconfdir}/yum.repos.d/surfd.repo
install -Dpm 0644 config/dnf/20-surfd.conf %{buildroot}%{_datadir}/dnf5/libdnf.conf.d/20-surfd.conf

%check
grep -q '^ID=surfd$' %{buildroot}%{_prefix}/lib/os-release
grep -q '^VERSION_ID=%{version}$' %{buildroot}%{_prefix}/lib/os-release
! grep -n '@[A-Z_]*@' %{buildroot}%{_prefix}/lib/os-release %{buildroot}%{_rpmmacrodir}/macros.dist

%files
%license LICENSE
%{_prefix}/lib/os-release
%{_sysconfdir}/os-release
%{_sysconfdir}/surfd-release
%{_sysconfdir}/system-release
%{_sysconfdir}/redhat-release
%{_sysconfdir}/system-release-cpe
%config(noreplace) %{_sysconfdir}/issue
%config(noreplace) %{_sysconfdir}/issue.net
%config(noreplace) %{_sysconfdir}/yum.repos.d/surfd.repo
%{_presetdir}/85-surfd.preset
%{_presetdir}/90-default.preset
%{_presetdir}/99-default-disable.preset
%{_userpresetdir}/90-default-user.preset
%{_userpresetdir}/99-default-disable.preset
%{_rpmmacrodir}/macros.dist
%dir %{_datadir}/dnf5
%dir %{_datadir}/dnf5/libdnf.conf.d
%{_datadir}/dnf5/libdnf.conf.d/20-surfd.conf

%changelog
* Mon Oct 19 2026 surfd contributors <surfd@example.invalid> - 44-1
- Initial release for Fedora 44
