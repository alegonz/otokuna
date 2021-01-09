HERE:=$(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))
WORKDIR:=$(HERE)
include $(WORKDIR)/Makefile.venv
