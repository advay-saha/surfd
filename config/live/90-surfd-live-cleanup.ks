# Installed as /usr/share/anaconda/post-scripts/90-surfd-live-cleanup.ks
# Anaconda runs this on the freshly installed system after a live install,
# so nothing from the live session leaks into it.
%post
cp -f /usr/share/surfd/greetd/config.toml /etc/surfd/greetd/config.toml
rm -f /etc/sudoers.d/surfd-live
if id liveuser >/dev/null 2>&1; then
    userdel --remove liveuser || :
fi
systemctl disable surfd-livesys.service 2>/dev/null || :
rpm -e --nodeps surfd-live surfd-installer 2>/dev/null || :
%end
