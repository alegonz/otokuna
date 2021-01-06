WORKDIR:=..
include ../Makefile.venv

.PHONY: setup
setup: venv
	$(VENV)/pip install -e .[dev]

.PHONY: test
test: venv
	$(VENV)/pytest tests/
