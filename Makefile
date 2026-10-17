# REGISTA developer commands: the targets of CLAUDE.md "Commands".
# Recipes are plain commands, so they run under sh (Linux, macOS, CI) and cmd.exe (Windows).
# Windows: winget install --id ezwinports.make -e

SEED ?= 7

.DEFAULT_GOAL := help
.PHONY: help sync hooks test lint format precommit league golden calibrate analyze serve \
	web-install web-dev web-test web-lint web-build check up

help: # list the targets; each one is described by its comment below
	@echo Targets: sync hooks test lint format precommit league golden calibrate analyze serve web-install web-dev web-test web-lint web-build check up

# --- Python workspace -------------------------------------------------------------------
sync: # install the workspace and dev tools from uv.lock
	uv sync

hooks: # install the git pre-commit hooks: ruff, ruff-format, gitleaks
	uv run pre-commit install

test: # fast unit tests for regista-sim and regista-core
	uv run pytest -q

lint: # ruff lint and format check, exactly as CI runs them
	uv run ruff check .
	uv run ruff format --check .

format: # auto-fix lint findings, then format
	uv run ruff check --fix .
	uv run ruff format .

precommit: # every pre-commit hook on all files
	uv run pre-commit run --all-files

# --- Simulator and analytics: Phase 1 and Phase 2 ----------------------------------------
league:
	uv run regista-sim league generate --seed $(SEED) --out data/league

golden:
	uv run regista-sim match run --scenario golden --seed $(SEED) --out data/golden

calibrate:
	uv run regista-sim calibrate --matches 40 --out data/calibration

analyze:
	uv run regista-core analyze data/golden

# --- Core service ---------------------------------------------------------------------------
serve: # FastAPI on :8000; BUS=memory and LLM_MODE=template unless .env says otherwise
	uv run regista-core serve

# --- Web: apps/web ---------------------------------------------------------------------------
web-install:
	pnpm -C apps/web install

web-dev: # Vite dev server on http://localhost:5173
	pnpm -C apps/web dev

web-test:
	pnpm -C apps/web test

web-lint:
	pnpm -C apps/web lint

web-build: # type-check, then production build
	pnpm -C apps/web build

# --- Everything CI checks, locally --------------------------------------------------------
check: lint test web-lint web-test web-build

# --- Azure: Phase 3 -----------------------------------------------------------------------
up: # provision and deploy with azd; run `azd auth login` once first
	azd up
