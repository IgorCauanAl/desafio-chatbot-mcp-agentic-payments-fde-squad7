.PHONY: install migrate run format lint typecheck test check

install:
	uv sync

migrate:
	uv run alembic upgrade head

run:
	uv run uvicorn app.main:app --reload --port 8000

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy app

test:
	uv run pytest -q

check: lint typecheck test
