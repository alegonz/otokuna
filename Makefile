include Makefile.venv

.PHONY: test
test: venv
	$(VENV)/pytest tests/
