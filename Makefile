PY ?= .venv/bin/python
PIP ?= .venv/bin/pip
PYTEST ?= .venv/bin/pytest
RUFF ?= .venv/bin/ruff
ALEMBIC ?= .venv/bin/alembic
PROFILE ?= default
SLUG ?=

.PHONY: help
help:  ## Print available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- setup -------------------------------------------------------------------

.PHONY: venv
venv:  ## Create .venv (python3.12) — idempotent
	@test -d .venv || python3.12 -m venv .venv
	@$(PIP) install --upgrade pip >/dev/null
	@echo "venv ok: $(PY)"

.PHONY: install
install: venv  ## Install runtime + dev dependencies into .venv
	$(PIP) install -r requirements-dev.txt

.PHONY: env
env:  ## Copy .env.example → .env if missing
	@test -f .env || (cp .env.example .env && echo "created .env from .env.example — edit before running")

# --- daily dev ---------------------------------------------------------------

.PHONY: test
test:  ## Run the full pytest suite
	$(PYTEST) -q

.PHONY: lint
lint:  ## Run ruff check + format --check
	$(RUFF) check .
	$(RUFF) format --check .

.PHONY: fix
fix:  ## Auto-fix ruff issues and reformat
	$(RUFF) check --fix .
	$(RUFF) format .

.PHONY: bot
bot:  ## Run the bot locally in long-polling mode
	$(PY) -m app.bot_main

.PHONY: api
api:  ## Run the FastAPI app with autoreload
	.venv/bin/uvicorn app.main:app --reload

# --- profiles (content layer) -----------------------------------------------

.PHONY: profiles
profiles:  ## List all content profiles with their company names
	$(PY) -m app.scripts.profiles list

.PHONY: validate-profile
validate-profile:  ## Validate a profile — usage: make validate-profile PROFILE=auto_service
	$(PY) -m app.scripts.profiles validate $(PROFILE)

.PHONY: new-client
new-client:  ## Scaffold a new client profile — usage: make new-client SLUG=acme [PROFILE=auto_service]
	@test -n "$(SLUG)" || (echo "Usage: make new-client SLUG=<name> [PROFILE=<source>]" && exit 1)
	$(PY) -m app.scripts.profiles new $(SLUG) --from $(PROFILE)

# --- database / migrations ---------------------------------------------------

.PHONY: migrate
migrate:  ## Apply Alembic migrations to head
	$(ALEMBIC) upgrade head

.PHONY: revision
revision:  ## Create a new Alembic revision — usage: make revision MSG="short message"
	@test -n "$(MSG)" || (echo "Usage: make revision MSG=\"short message\"" && exit 1)
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

.PHONY: seed
seed:  ## Seed categories / questions from the active CONTENT_PROFILE
	$(PY) -m app.seed

# --- docker (local / dev) ----------------------------------------------------

.PHONY: dev-up
dev-up:  ## Start the dev stack (postgres + redis + bot + api + migrate)
	docker compose up -d

.PHONY: dev-down
dev-down:  ## Stop and remove the dev stack (volumes preserved)
	docker compose down

.PHONY: dev-logs
dev-logs:  ## Tail logs from the bot container
	docker compose logs -f bot

.PHONY: dev-rebuild
dev-rebuild:  ## Rebuild containers after code changes
	docker compose build bot api worker migrate
	docker compose up -d

# --- docker (production) -----------------------------------------------------

.PHONY: prod-up
prod-up:  ## Start the production stack
	docker compose -f docker-compose.prod.yml up -d

.PHONY: prod-down
prod-down:  ## Stop and remove the prod stack (volumes preserved)
	docker compose -f docker-compose.prod.yml down

.PHONY: prod-logs
prod-logs:  ## Tail logs from the prod bot container
	docker compose -f docker-compose.prod.yml logs -f bot

.PHONY: prod-migrate
prod-migrate:  ## Run migrations against the prod stack
	docker compose -f docker-compose.prod.yml run --rm migrate
