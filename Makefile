HERE:=$(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))
WORKDIR:=$(HERE)

# TODO: Consider disabling automatic installation of requirements files
#   and setup.py in Makefile.venv, and instead do the installation explicitly.
REQUIREMENTS_TXT=requirements/svc.txt requirements/dev.txt

include $(WORKDIR)/Makefile.venv

# Install pip-compile to pin app dependencies
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
# After any of the above run:
#      make venv PIP_COMPILE_ARGS="-q"
ifneq ($(PIP_COMPILE_ARGS),)
requirements/svc.txt: requirements/svc.in | $(PIP_COMPILE)
	# TODO: upgrade serverless-python-requirements to >=5.1.1 to avoid sed workaround.
	#   See: https://github.com/UnitedIncome/serverless-python-requirements/issues/36
	CUSTOM_COMPILE_COMMAND="make $@" $(PIP_COMPILE) $(PIP_COMPILE_ARGS) -q --output-file $@ $<
	sed -i 's/^-e //' $@

requirements/dev.txt: requirements/dev.in requirements/svc.txt | $(PIP_COMPILE)
	CUSTOM_COMPILE_COMMAND="make $@" $(PIP_COMPILE) $(PIP_COMPILE_ARGS) -q --output-file $@ $<
endif
