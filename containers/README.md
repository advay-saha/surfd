# surfd atomic variant (experimental)

An image-based surfd built on [`fedora-bootc`](https://docs.fedoraproject.org/en-US/bootc/).
The operating system is a container image; updates replace it atomically
and can be rolled back. Your home directory and `/etc` changes are kept.

It uses the same package list as the live ISO (`packages-<arch>.txt`,
generated from the kickstarts by `tools/ks_packages.py`).

## Build

```sh
./build.sh rpms                     # surfd RPMs into out/repo
./build.sh container                # localhost/surfd-bootc:44
```

## Make an installer ISO or a VM disk

```sh
sudo podman run --rm -it --privileged --pull=newer \
  --security-opt label=type:unconfined_t \
  -v ./output:/output \
  -v /var/lib/containers/storage:/var/lib/containers/storage \
  quay.io/centos-bootc/bootc-image-builder:latest \
  --type anaconda-iso --rootfs ext4 localhost/surfd-bootc:44
# or --type qcow2 for a VM disk
```

## Switch an existing Fedora Atomic / bootc system

```sh
sudo bootc switch --transport containers-storage localhost/surfd-bootc:44
sudo reboot
```

## Status and limitations

- Not built or booted in surfd's CI yet; treat it as a preview.
- `surfd-release` replaces `fedora-release-common` with `--allowerasing`;
  check `cat /etc/os-release` after the first boot.
- Package installs with `dnf` are not persistent on bootc systems; use
  Flatpak, toolbox/distrobox, or rebuild the image with your additions.
