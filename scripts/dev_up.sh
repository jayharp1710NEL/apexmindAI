#!/usr/bin/env bash
# Bootstrap the dev stack: bring up infra, migrate, seed, then run api + worker.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Creating .env from .env.example (fill in provider keys to use models)."
  cp .env.example .env
fi

echo "==> Starting Postgres + Redis"
docker compose up -d postgres redis

echo "==> Waiting for Postgres"
until docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-apex}" >/dev/null 2>&1; do
  sleep 1
done

echo "==> Running migrations"
docker compose run --rm api alembic upgrade head

echo "==> Seeding prompts + tool registry"
docker compose run --rm api python ../scripts/seed_prompts.py || true
docker compose run --rm api python ../scripts/seed_tool_registry.py || true

echo "==> Starting api + tool-worker"
docker compose up api tool-worker
