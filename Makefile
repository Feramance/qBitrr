.DEFAULT_GOAL := help

ROOT_DIR:=$(abspath .)
WEBUI_DIR:=$(ROOT_DIR)/webui
VENV_DIR:=$(ROOT_DIR)/.venv

ifeq ($(OS),Windows_NT)
	PYTHON ?= python
	VENV_PYTHON := ./.venv/Scripts/python.exe
	WEBUI_BUILD := if exist "$(WEBUI_DIR)\package.json" (pushd "$(WEBUI_DIR)" && npm ci && npm run build && popd)
else
	PYTHON ?= $(shell \
		if command -v python3 >/dev/null 2>&1; then \
			echo python3; \
		elif command -v python >/dev/null 2>&1; then \
			echo python; \
		else \
			echo python3; \
		fi \
	)
	VENV_PYTHON := ./.venv/bin/python
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
	"$(VENV_PYTHON)" -m pip install --upgrade pip
	"$(VENV_PYTHON)" -m pip install --upgrade setuptools==69.5.1
	"$(VENV_PYTHON)" -m pip install --upgrade wheel
	"$(VENV_PYTHON)" -m pip install --upgrade pre-commit
	$(MAKE) syncenv
syncenv:
	"$(VENV_PYTHON)" -m pip install --upgrade pip
	"$(VENV_PYTHON)" -m pip install -e ".[all]"
	"$(VENV_PYTHON)" -m pre_commit install
	@$(WEBUI_BUILD)
help:
	@echo "$$HELP_BODY"
