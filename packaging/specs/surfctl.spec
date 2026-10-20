# surfctl — the surfd configuration tool (and surfd-hwprobe)
Name:           surfctl
Version:        0.1.0
Release:        1%{?dist}
Summary:        Configure the surfd desktop from one TOML file
License:        MIT
URL:            https://github.com/advay-saha/surfd
Source0:        surfd-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3
# python3-devel brings the Python RPM macros (python3_sitelib and friends)
BuildRequires:  python3-devel
BuildRequires:  python3-pytest
BuildRequires:  python3-tomlkit

Requires:       python3
Requires:       python3-tomlkit
# Runtime helpers surfctl calls (each is optional at the call site)
Recommends:     fuzzel
Recommends:     grim
Recommends:     slurp
Recommends:     wl-clipboard

%description
surfctl reads ~/.config/surfd/surfd.toml and generates the Sway, Waybar,
mako, fuzzel, foot, swaylock, GTK and Qt configuration for the surfd
desktop, then applies it to the running session. Themes are drop-in
folders; every change keeps a reversible backup.

%package -n surfd-hwprobe
Summary:        Detect hardware and suggest drivers for surfd
Requires:       python3
Recommends:     pciutils

%description -n surfd-hwprobe
surfd-hwprobe inspects /sys, /proc and the kernel log and suggests extra
drivers or firmware (NVIDIA, Broadcom Wi-Fi, SOF audio, missing firmware
files, virtual-machine guest tools) with the exact commands to run. It
never installs anything by itself.

%prep
%autosetup -n surfd-%{version}

%build
# Pure Python; nothing to build.

%install
install -d %{buildroot}%{python3_sitelib}
cp -a src/surfctl/surfd %{buildroot}%{python3_sitelib}/
find %{buildroot}%{python3_sitelib}/surfd -name '__pycache__' -prune -exec rm -rf {} +
install -Dpm 0755 src/surfctl/bin/surfctl %{buildroot}%{_bindir}/surfctl
install -Dpm 0755 src/hwprobe/surfd_hwprobe.py %{buildroot}%{_bindir}/surfd-hwprobe
sed -i '1s|^#!.*|#!%{__python3} -sP|' %{buildroot}%{_bindir}/surfctl %{buildroot}%{_bindir}/surfd-hwprobe
install -Dpm 0644 docs/man/surfctl.1 %{buildroot}%{_mandir}/man1/surfctl.1
install -Dpm 0644 docs/man/surfd-hwprobe.1 %{buildroot}%{_mandir}/man1/surfd-hwprobe.1

%check
export PYTHONDONTWRITEBYTECODE=1
%{__python3} -m pytest -q -p no:cacheprovider src/surfctl/tests src/hwprobe/tests
PYTHONPATH=%{buildroot}%{python3_sitelib} %{buildroot}%{_bindir}/surfctl --version

%files
%license LICENSE
%doc docs/customization.md
%{_bindir}/surfctl
%{_mandir}/man1/surfctl.1*
%{python3_sitelib}/surfd

%files -n surfd-hwprobe
%license LICENSE
%doc docs/hardware.md
%{_bindir}/surfd-hwprobe
%{_mandir}/man1/surfd-hwprobe.1*

%changelog
* Mon Oct 19 2026 surfd contributors <surfd@example.invalid> - 0.1.0-1
- Initial release
