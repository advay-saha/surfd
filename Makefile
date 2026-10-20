# surfd developer tasks. `make check` is what CI runs on every push.
PY      ?= python3
GUI_PY  ?= $(PY)
FEDORA  ?= 44
ART     ?= build/art

SHELL_SCRIPTS := build.sh tools/*.sh packaging/*.sh src/session/surfd-session \
                 src/session/libexec/* config/live/surfd-livesys

.PHONY: help check lint test rpms rpm-test art screenshots ks iso container container-packages docs clean

help:
	@echo "make check            lint + tests (what CI runs)"
	@echo "make rpms             build RPMs on Fedora (./build.sh rpms)"
	@echo "make rpm-test         build RPMs on a non-Fedora host (test macros)"
	@echo "make iso              build the live ISO (Fedora host, root)"
	@echo "make art              regenerate SVG artwork and render PNG/JPEG"
	@echo "make screenshots      headless session + GUI screenshots into docs/screenshots"
	@echo "make container-packages  refresh containers/packages-*.txt from the kickstarts"

check: lint test

lint:
	shellcheck -x $(SHELL_SCRIPTS)
	ruff check src theme/tools tools
	cd kickstarts && for a in x86_64 aarch64; do ksvalidator -v F$(FEDORA) surfd-$$a.ks || exit 1; done
	ksvalidator -v F$(FEDORA) config/live/90-surfd-live-cleanup.ks
	desktop-file-validate src/settings/data/*.desktop src/installer/data/*.desktop src/session/surfd.desktop
	appstreamcli validate --no-net src/settings/data/*.metainfo.xml
	$(PY) -c 'import tomllib,glob; [tomllib.load(open(f,"rb")) for f in ["config/defaults/surfd.toml", *glob.glob("theme/themes/*/theme.toml"), *glob.glob("wallpapers/third-party/themes/*/theme.toml")]]'
	@for a in x86_64 aarch64; do \
	  $(PY) tools/ks_packages.py --arch $$a | diff -q - containers/packages-$$a.txt >/dev/null \
	    || { echo "containers/packages-$$a.txt is stale: run make container-packages"; exit 1; }; done
	@$(PY) tools/gen_settings_doc.py | diff -q - docs/settings-reference.md >/dev/null \
	  || { echo "docs/settings-reference.md is stale: run make docs"; exit 1; }
	@echo "lint: OK"

test:
	$(PY) -m pytest -q src/surfctl/tests src/hwprobe/tests src/installer/tests
	$(GUI_PY) -m pytest -q src/settings/tests

rpms:
	./build.sh --releasever $(FEDORA) rpms

rpm-test:
	packaging/build-rpms.sh --out out/repo -- --nodeps --load "$(CURDIR)/packaging/test/fedora-compat.macros"

ks:
	./build.sh --releasever $(FEDORA) ks

iso:
	sudo ./build.sh --releasever $(FEDORA) --selinux-permissive iso

container:
	./build.sh --releasever $(FEDORA) container

docs:
	$(PY) tools/gen_settings_doc.py > docs/settings-reference.md

container-packages:
	for a in x86_64 aarch64; do $(PY) tools/ks_packages.py --arch $$a > containers/packages-$$a.txt; done

art:
	$(PY) theme/tools/make_art.py
	rm -rf $(ART) && $(PY) theme/tools/render.py $(ART)

screenshots: art
	tools/headless-screenshot.sh $(ART) docs/screenshots tide dark tiling
	for t in low-poly-mountain:dark tokyo-street:light red-cave:dark japanese-garden:dark bitter-coast:light \
	         plants:dark scenery-sunset:dark tropical-beach:light; do \
	  tools/headless-screenshot.sh $(ART) docs/screenshots $${t%%:*} $${t##*:} showcase || exit 1; done
	tools/gui-screenshot.sh $(ART) docs/screenshots $(GUI_PY) low-poly-mountain dark
	tools/installer-screenshot.sh $(ART) docs/screenshots $(GUI_PY)

clean:
	rm -rf out build .pytest_cache .ruff_cache
	find . -name __pycache__ -prune -exec rm -rf {} +
