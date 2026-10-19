# surfd-boot-aarch64.ks — aarch64 boot and CPU packages (used by live and netinstall)

%packages --exclude-weakdeps
shim-aa64
grub2-efi-aa64
grub2-efi-aa64-cdboot
efibootmgr
%end
