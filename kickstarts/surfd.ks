# surfd.ks — top-level composition for the surfd live image.
#
# surfd is a Fedora Remix. It is based on Fedora Linux but is NOT an
# official Fedora project and is not endorsed by the Fedora Project.
#
# Do not build this file directly: build.sh flattens the per-architecture
# wrapper (surfd-x86_64.ks / surfd-aarch64.ks), which %includes this file,
# and injects the local surfd RPM repository. See docs/build.md.
#
# Layout:
#   surfd-repos.ks    Fedora + updates repositories ($releasever-driven)
#   surfd-base.ks     OS core: locale, security, services, kernel, firmware
#   surfd-desktop.ks  Sway session, theming, apps, surfd components
#   surfd-live.ks     live-media-only bits: installer, dracut-live, live user

%include surfd-repos.ks
%include surfd-base.ks
%include surfd-desktop.ks
%include surfd-live.ks
