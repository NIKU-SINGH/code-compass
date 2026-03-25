.PHONY: install install-web dev build clean

install:
	pip install -e packages/core
	pip install -e apps/cli
	pip install -e apps/mcp

install-web:
	cd apps/web && pnpm install

dev:
	cd apps/web && pnpm dev

build:
	cd apps/web && pnpm build
	cp -r apps/web/dist/* packages/core/src/compass_core/server/static/

clean:
	rm -rf packages/core/src/compass_core/server/static/*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
