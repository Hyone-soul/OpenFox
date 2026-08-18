.PHONY: install test lint run cli server clean desktop-dev desktop-build desktop-package

install:
	pip install -e ".[dev]"

test:
	pytest -v

lint:
	ruff check src tests

cli:
	OpenFox

server:
	openfox-server --host 0.0.0.0 --port 8000

# Desktop (Electron) commands
desktop-dev:
	cd desktop && npm run dev

desktop-build:
	cd desktop && npm run build

desktop-package:
	cd desktop && npm run build:electron

clean:
	rm -rf build dist *.egg-info .pytest_cache logs/*.log
	rm -rf desktop/dist desktop/node_modules/.cache
