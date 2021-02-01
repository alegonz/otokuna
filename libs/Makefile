HERE:=$(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))
include $(HERE)/../Makefile

.PHONY: test
test: venv
	$(VENV)/pytest tests/
