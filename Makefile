.PHONY: test lint web-test

test:
	cd backend && .venv/bin/python -m pytest

lint:
	cd backend && .venv/bin/python -m compileall -q app tests

web-test:
	cd web && npm run test

