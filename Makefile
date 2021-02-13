HERE:=$(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))
WORKDIR:=$(HERE)

include $(WORKDIR)/Makefile.venv

# Install pip-compile to pin svc dependencies
# pip-tools is pinned to a version where a workaround for emitting relative paths
# with pip-compile works.
PIP_COMPILE=$(VENV)/pip-compile
$(PIP_COMPILE): | $(VENV)
	$(VENV)/pip install pip-tools==5.5.0
	touch $@

# How to modify dependencies:
# * To change requirements, edit the requirements/*.in files as necessary.
# * To upgrade a specific pinned package (e.g. freezegun of requirements/dev.txt):
#      make -W requirements/dev.{in,txt} PIP_COMPILE_ARGS="-P freezegun"
# * To upgrade all pinned packages (e.g. of requirements/svc.txt):
#      make -W requirements/svc.{in,txt} PIP_COMPILE_ARGS="-U"
requirements/svc.txt: requirements/svc.in libs/setup.py | $(PIP_COMPILE)
	CUSTOM_COMPILE_COMMAND="make $@" $(PIP_COMPILE) $(PIP_COMPILE_ARGS) -q --output-file $@ $<

requirements/dev.txt: requirements/dev.in requirements/svc.txt | $(PIP_COMPILE)
	CUSTOM_COMPILE_COMMAND="make $@" $(PIP_COMPILE) $(PIP_COMPILE_ARGS) -q --output-file $@ $<

.PHONY: setup
setup: venv
	$(VENV)/pip install -r requirements/svc.txt -r requirements/dev.txt
