.PHONY: all dev mock test e2e bench lint typecheck seed ci

all: lint typecheck test

dev:
	bash scripts/dev.sh

mock:
	npx @stoplight/prism-cli mock openapi.yaml -p 4010

test:
	cd backend && uv run pytest -q --cov=app
	cd frontend && npm run test:coverage

e2e:
	cd frontend && LLM_MOCK=1 npm run test:e2e

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npm run format:check

typecheck:
	cd frontend && npm run typecheck

ci:
	bash scripts/ci-local.sh

bench:
	@if [ -d "backend/app/bench" ]; then \
		cd backend && uv run python -m app.bench; \
	else \
		echo "Bench harness not yet implemented (backend/app/bench/ - requirement R12)"; \
	fi

seed:
	@if [ -f "backend/app/seed.py" ]; then \
		cd backend && uv run python -m app.seed $(if $(CASE),--case=$(CASE),); \
	else \
		echo "Seed case reset not yet implemented (seed CASE=$(CASE))"; \
	fi
