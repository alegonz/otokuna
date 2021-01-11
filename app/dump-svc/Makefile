HERE:=$(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))
include $(HERE)/../Makefile

requirements.txt: requirements.in | $(PIP_COMPILE)
	# TODO: upgrade serverless-python-requirements to >=5.1.1 to avoid sed workaround.
	#   See: https://github.com/UnitedIncome/serverless-python-requirements/issues/36
	CUSTOM_COMPILE_COMMAND="make $@" $(PIP_COMPILE) -q -o - $< | sed 's/^-e //' > $@

.PHONY: _sls_deps
_sls_deps: requirements.txt | serverless

# TODO:
#  Add installation of the following plugins:
#  - serverless-python-requirements
#  - serverless-step-functions
#  Could be done via a target that requires a plugins.in file that and generates
#  the package-lock.json file.

ifndef SERVERLESS_ORG
$(error SERVERLESS_ORG is not set)
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
