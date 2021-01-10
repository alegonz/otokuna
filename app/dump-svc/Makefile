HERE:=$(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))
include $(HERE)/../Makefile

requirements.txt: requirements.in | $(PIP_COMPILE)
	# TODO: upgrade serverless-python-requirements to >=5.1.1 to avoid sed workaround.
	#   See: https://github.com/UnitedIncome/serverless-python-requirements/issues/36
	CUSTOM_COMPILE_COMMAND="make $@" $(PIP_COMPILE) -q -o - $< | sed 's/^-e //' > $@

.PHONY: _sls_deps
_sls_deps: serverless.yml handler.py requirements.txt | serverless

.PHONY: package
package: _sls_deps
	sls package --org $(SERVERLESS_ORG)

.PHONY: _sls_deps
deploy: _sls_deps
	sls deploy --org $(SERVERLESS_ORG)
