.PHONY: install test lint run-example run-ui clean build

install:
	pip install -e ".[dev,ui]"

test:
	pytest --cov=clinicalcompress --cov-report=term-missing

lint:
	ruff check clinicalcompress tests examples

run-example:
	python examples/quickstart.py

run-ui:
	uvicorn webui.app:app --reload --port 8000

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +

build:
	python -m build
