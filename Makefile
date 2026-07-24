.PHONY: test lint web-test local-up local-down

test:
	cd backend && .venv/bin/python -m pytest

lint:
	cd backend && .venv/bin/python -m compileall -q app tests

web-test:
	cd web && npm run lint && npm run test && npm run build

local-up:
	docker compose -f docker-compose.local.yml up --build

local-down:
	docker compose -f docker-compose.local.yml down -v
