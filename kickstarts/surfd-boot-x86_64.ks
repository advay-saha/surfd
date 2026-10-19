# surfd-boot-x86_64.ks — x86_64 boot and CPU packages (used by live and netinstall)

%packages --exclude-weakdeps
# UEFI (with Secure Boot via Fedora's signed shim) and BIOS boot for the ISO
shim-x64
grub2-efi-x64
grub2-efi-x64-cdboot
grub2-pc
grub2-pc-modules
grub2-tools-extra
efibootmgr
# CPU microcode and Intel thermal management
microcode_ctl
amd-ucode-firmware
thermald
# Intel hardware video decoding (free build; RPM Fusion has the full one)
libva-intel-media-driver
%end
