.PHONY: install install-web dev build clean openapi gen-api

install:
	pip install -e packages/core
	pip install -e packages/server
	pip install -e packages/cli
	pip install -e packages/mcp

install-web:
	cd apps/web && pnpm install

dev:
	cd apps/web && pnpm dev

build:
	cd apps/web && pnpm build
	cp -r apps/web/dist/* packages/server/src/compass_server/static/

clean:
	rm -rf packages/server/src/compass_server/static/*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

openapi:
	uv run python packages/server/scripts/dump_openapi.py .build/openapi.json

gen-api: openapi
	cd apps/web && pnpm gen:api
	uv run python packages/server/scripts/dump_web_limits.py apps/web/src/lib/limits.ts
