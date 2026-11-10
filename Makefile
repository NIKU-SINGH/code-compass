.PHONY: install install-web dev build web-static clean openapi gen-api

install:
	uv sync --all-packages --all-groups

install-web:
	cd apps/web && pnpm install

dev:
	cd apps/web && pnpm dev

build:
	cd apps/web && pnpm build

# The web UI as static files inside compass_server, so the published package serves it.
# An empty NEXT_PUBLIC_API_URL makes the UI call the API on the same origin.
web-static:
	cd apps/web && STATIC_EXPORT=1 NEXT_PUBLIC_API_URL= pnpm build
	rm -rf packages/server/src/compass_server/static
	cp -r apps/web/out packages/server/src/compass_server/static

clean:
	rm -rf packages/server/src/compass_server/static/*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

openapi:
	uv run python packages/server/scripts/dump_openapi.py .build/openapi.json

gen-api: openapi
	cd apps/web && pnpm gen:api
	uv run python packages/server/scripts/dump_web_limits.py apps/web/src/lib/limits.ts
