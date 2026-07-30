.PHONY: install test sync clean setup-hooks

install:
	uv tool install --force .

test:
	uv run pytest

sync:
	uv sync --extra dev

setup-hooks:
	git config core.hooksPath .githooks

clean:
	rm -rf .venv/ .venv-dev/ __pycache__/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
