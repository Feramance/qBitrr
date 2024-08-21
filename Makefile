.DEFAULT_GOAL := help

PYTHON ?= python

ROOT_DIR:=$(dir $(abspath $(lastword $(MAKEFILE_LIST))))

ifneq ($(wildcard $(ROOT_DIR)/.venv/.),)
	VENV_PYTHON = $(ROOT_DIR)/.venv/bin/python
else
	VENV_PYTHON = $(PYTHON)
endif

define HELP_BODY
Usage:
  make <command>

Commands:
  reformat                   Reformat all files being tracked by git.
  bumpdeps                   Run script bumping dependencies.
  newenv                     Create or replace this project's virtual environment.
  syncenv                    Sync this project's virtual environment to Red's latest dependencies.
endef
export HELP_BODY

# Python Code Style
reformat:
	pre-commit run --all-files

# Dependencies
bumpdeps:
	pip-compile -o requirements.txt --upgrade
	pip-compile -o requirements.dev.txt --extra dev --upgrade
	pip-compile -o requirements.fast.txt --extra fast --upgrade
	pip-compile -o requirements.all.txt --extra all --upgrade

# Development environment
newenv:
	$(PYTHON) -m venv --clear .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -U setuptools==69.5.1
	.venv/bin/pip install -U wheel
	$(MAKE) syncenv
syncenv:
	python.exe -m pip install --upgrade pip
	pip install -Ur requirements.all.txt
help:
	@echo "$$HELP_BODY"
