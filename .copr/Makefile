# Copr "make srpm" source method. Copr runs:
#   make -f .copr/Makefile srpm outdir=<dir> spec=<path to spec>
# See https://docs.pagure.org/copr.copr/user_documentation.html#make-srpm
outdir ?= $(CURDIR)/out/srpm
spec   ?=

srpm:
	dnf -y install --setopt=install_weak_deps=False git tar gzip rpm-build findutils
	./packaging/build-rpms.sh --srpm-only --out "$(outdir)" \
	  $(if $(spec),--spec $(basename $(notdir $(spec))))
