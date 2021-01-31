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

~/.serverless/bin/sls:
	curl -o- -L https://slss.io/install | bash

.PHONY: serverless
serverless: ~/.serverless/bin/sls

package-lock.json: plugins.in
	@for plugin_name in $$(cat plugins.in); do \
	    sls plugin install --name $${plugin_name} --stage $(STAGE); \
	done

.PHONY: plugins | serverless
plugins: package-lock.json

.PHONY: _sls_deps
_sls_deps: plugins requirements/svc.txt | serverless

ifneq (,$(filter $(MAKECMDGOALS),package deploy remove))
ifndef SERVERLESS_ORG
$(error SERVERLESS_ORG is not set)
endif
endif
STAGE?=dev
SERVERLESS_ARGS=--stage $(STAGE) --org $(SERVERLESS_ORG)

export GIT_REPO_NAME = $(shell basename "$$(git rev-parse --show-toplevel)")
export GIT_BRANCH = $(shell git rev-parse --abbrev-ref HEAD)
export GIT_COMMIT_HASH_SHORT = $(shell git rev-parse --short HEAD)
export GIT_IS_DIRTY = $(shell if [ -n "$$(git diff HEAD)" ]; then echo true; else echo false; fi)

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
