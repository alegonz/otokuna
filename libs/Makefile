HERE:=$(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))
include $(HERE)/../Makefile

.PHONY: setup
setup: venv
	$(VENV)/pip install -e .[dev]

.PHONY: test
test: venv
	$(VENV)/pytest tests/
