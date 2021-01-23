# TODO: Consider disabling automatic installation of requirements files
#   and setup.py in Makefile.venv, and instead do the installation explicitly.
REQUIREMENTS_TXT=requirements/svc.txt requirements/dev.txt

HERE:=$(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))
include $(HERE)/../Makefile

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

.PHONY: test
test: venv
	$(VENV)/pytest .

.PHONY: _sls_deps
_sls_deps: requirements/svc.txt | serverless

# TODO:
#  Add installation of the following plugins:
#  - serverless-python-requirements
#  - serverless-step-functions
#  Could be done via a target that requires a plugins.in file that and generates
#  the package-lock.json file.

ifneq (,$(filter $(MAKECMDGOALS),package deploy remove))
ifndef SERVERLESS_ORG
$(error SERVERLESS_ORG is not set)
endif
endif
STAGE?=dev
SERVERLESS_ARGS=--stage $(STAGE) --org $(SERVERLESS_ORG)

# It is safer to clean the cache of serverless-python-requirements
# to avoid missing packaging changes to the libs.
.PHONY: _clean_sls_py_req
_clean_sls_py_req: | serverless
	sls requirements clean $(SERVERLESS_ARGS)
	sls requirements cleanCache $(SERVERLESS_ARGS)

.PHONY: package
package: _sls_deps _clean_sls_py_req
	sls package $(SERVERLESS_ARGS)

.PHONY: _sls_deps
deploy: _sls_deps _clean_sls_py_req
	sls deploy $(SERVERLESS_ARGS)

.PHONY: remove
remove: | serverless
	sls remove $(SERVERLESS_ARGS)
