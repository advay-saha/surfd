# surfd-repos.ks — package sources.
#
# $releasever and $basearch are substituted by the installer from
# `livemedia-creator --releasever N` and the build host architecture.
# The surfd component repository (local RPMs or Copr) is added by build.sh.

url --mirrorlist="https://mirrors.fedoraproject.org/mirrorlist?repo=fedora-$releasever&arch=$basearch"
repo --name=updates --mirrorlist="https://mirrors.fedoraproject.org/mirrorlist?repo=updates-released-f$releasever&arch=$basearch"
