# surfd-live.ks — things that only exist on the live/installer image.
#
# The live user, autologin and the "Install surfd" launcher come from the
# surfd-live package. Its service only acts when the kernel command line
# contains rd.live.image, and Anaconda removes the package from the
# installed system (see config/anaconda/post-scripts/90-surfd-live-cleanup.ks).

# Live media root filesystem; livemedia-creator sizes the image from this.
# The bootloader comes from lorax's live templates, not from Anaconda.
zerombr
clearpart --all
part / --size=8192 --fstype=ext4
bootloader --location=none
shutdown

%packages --exclude-weakdeps
surfd-live

# Installer: Anaconda's live installer (GTK), surfd-branded through the
# profile and stylesheet shipped in surfd-logos.
anaconda
anaconda-install-env-deps
anaconda-live
@anaconda-tools
# Anaconda pulls these by weak dependency on Fedora Workstation; not wanted
# on a live desktop image.
-fcoe-utils
-device-mapper-multipath

# Needed by dracut to build a live-bootable initramfs (dmsquash-live).
dracut-live

# Anaconda needs every locale available to offer language selection.
glibc-all-langpacks
%end

%post --erroronfail
systemctl enable surfd-livesys.service

# The live image should not refresh metadata or update firmware lists.
systemctl disable fwupd-refresh.timer 2>/dev/null || :

# Record build metadata for bug reports.
cat > /etc/surfd-build-info <<EOF
SURFD_IMAGE=live
BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
%end
