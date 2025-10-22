.DEFAULT_GOAL := help

PYTHON ?= python

ROOT_DIR:=$(abspath .)
WEBUI_DIR:=$(ROOT_DIR)/webui
VENV_DIR:=$(ROOT_DIR)/.venv

ifeq ($(OS),Windows_NT)
	VENV_PYTHON := ./.venv/Scripts/python.exe
	VENV_PIP := ./.venv/Scripts/pip.exe
	WEBUI_BUILD := if exist "$(WEBUI_DIR)\package.json" (pushd "$(WEBUI_DIR)" && npm ci && npm run build && popd)
else
	VENV_PYTHON := ./.venv/bin/python
	VENV_PIP := ./.venv/bin/pip
	WEBUI_BUILD := if [ -f "$(WEBUI_DIR)/package.json" ]; then \
		cd "$(WEBUI_DIR)" && npm ci && npm run build; \
	fi
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
	@echo "Dependencies are managed via setup.cfg extras; update versions there and adjust requirements*.txt if publishing to PyPI."

# Development environment
newenv:
	$(PYTHON) -m venv --clear ".venv"
	"$(VENV_PIP)" install -U pip
	"$(VENV_PIP)" install -U setuptools==69.5.1
	"$(VENV_PIP)" install -U wheel
	"$(VENV_PIP)" install -U pre-commit
	$(MAKE) syncenv
syncenv:
	"$(VENV_PYTHON)" -m pip install --upgrade pip
	"$(VENV_PYTHON)" -m pip install -e ".[all]"
	"$(VENV_PYTHON)" -m pre_commit install
	@$(WEBUI_BUILD)
help:
	@echo "$$HELP_BODY"
