.DEFAULT_GOAL := help

ROOT_DIR:=$(abspath .)
WEBUI_DIR:=$(ROOT_DIR)/webui
VENV_DIR:=$(ROOT_DIR)/.venv

ifeq ($(OS),Windows_NT)
	PYTHON ?= python
	PYTHON311 ?= $(shell \
		for cmd in python3.12 python3.13 python3.14 python3.11 python3 python; do \
			if command -v $$cmd >/dev/null 2>&1; then \
				version=$$($$cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null); \
				if [ "$$version" = "3.11" ] || [ "$$version" = "3.12" ] || [ "$$version" = "3.13" ] || [ "$$version" = "3.14" ]; then \
					echo $$cmd; \
					exit 0; \
				fi; \
			fi; \
		done; \
		echo ""; \
	)
	VENV_PYTHON := ./.venv/Scripts/python.exe
	WEBUI_BUILD := if [ -f "$(WEBUI_DIR)/package.json" ]; then \
		cd "$(WEBUI_DIR)" && npm ci && npm run build; \
	fi
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
	PYTHON311 ?= $(shell \
		for cmd in python3.12 python3.13 python3.14 python3.11 python3 python; do \
			if command -v $$cmd >/dev/null 2>&1; then \
				version=$$($$cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null); \
				if echo "$$version" | grep -qE "^3\.(1[1-9]|[2-9][0-9])$$"; then \
					echo $$cmd; \
					exit 0; \
				fi; \
			fi; \
		done; \
		echo ""; \
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
  docs-install               Install documentation dependencies.
  docs-serve                 Serve documentation locally with hot reload.
  docs-build                 Build documentation site.
  docs-deploy                Deploy documentation to GitHub Pages.
  docs-clean                 Clean documentation build artifacts.
  docs-check                 Check documentation links.
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
	@if [ -z "$(PYTHON311)" ]; then \
		echo "Error: Python 3.11 or higher is required but not found."; \
		echo "Please install Python 3.11+ and ensure it's in your PATH."; \
		echo "Tried: python3.12, python3.13, python3.14, python3.11, python3, python"; \
		exit 1; \
	fi
	@echo "Using Python: $(PYTHON311)"
	$(PYTHON311) -m venv --clear ".venv"
	"$(VENV_PYTHON)" -m pip install --upgrade pip
	"$(VENV_PYTHON)" -m pip install --upgrade setuptools==69.5.1
	"$(VENV_PYTHON)" -m pip install --upgrade wheel
	"$(VENV_PYTHON)" -m pip install --upgrade pre-commit
	"$(MAKE)" syncenv
syncenv:
	"$(VENV_PYTHON)" -m pip install --upgrade pip
	"$(VENV_PYTHON)" -m pip install -e ".[all]"
	"$(VENV_PYTHON)" -m pre_commit install
	@$(WEBUI_BUILD)
help:
	@echo "$$HELP_BODY"

# Documentation
.PHONY: docs-install docs-serve docs-build docs-deploy docs-clean docs-check

docs-install:
	"$(VENV_PYTHON)" -m pip install -r requirements.docs.txt

docs-serve:
	"$(VENV_PYTHON)" -m mkdocs serve --dev-addr 127.0.0.1:8000

docs-build:
	"$(VENV_PYTHON)" -m mkdocs build

docs-build-strict:
	"$(VENV_PYTHON)" -m mkdocs build --strict

docs-deploy:
	"$(VENV_PYTHON)" -m mkdocs gh-deploy --force

docs-clean:
	rm -rf site/

docs-check:
	"$(VENV_PYTHON)" -m mkdocs build --strict
	@echo "Link checking requires linkchecker to be installed: pip install linkchecker"
	@command -v linkchecker >/dev/null 2>&1 && linkchecker site/ || echo "Skipping link check (linkchecker not installed)"
