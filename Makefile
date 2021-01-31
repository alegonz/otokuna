HERE:=$(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))
WORKDIR:=$(HERE)
include $(WORKDIR)/Makefile.venv

# Install pip-compile to pin app dependencies
# pip-tools is pinned to a version where a workaround for emitting relative paths
# with pip-compile works.
PIP_COMPILE=$(VENV)/pip-compile
$(PIP_COMPILE): | $(VENV)
	$(VENV)/pip install pip-tools==5.5.0
	touch $@
