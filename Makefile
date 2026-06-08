# FolderKnowledgeSiteGeneratorForAI — Local Development Checks
#
# Usage:
#   make check   — Run all checks (lint, format-check, type-check, test)
#   make format  — Auto-format code with ruff
#   make lint    — Lint with ruff (no fix)
#   make type    — Type-check with mypy
#   make test    — Run test suite

.PHONY: check format lint type test

check:
	@echo "=== ruff check ==="
	ruff check src/ tests/
	@echo ""
	@echo "=== ruff format check ==="
	ruff format --check src/ tests/
	@echo ""
	@echo "=== mypy ==="
	mypy src/ --config-file pyproject.toml
	@echo ""
	@echo "=== pytest ==="
	pytest tests/ -v

format:
	ruff format src/ tests/

lint:
	ruff check src/ tests/

type:
	mypy src/ --config-file pyproject.toml

test:
	pytest tests/ -v