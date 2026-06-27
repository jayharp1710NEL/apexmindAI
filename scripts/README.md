# scripts/

Operational scripts (added in later build steps):

- `prove_model_agnostic.py` — prints a completion from each configured provider
  via the router, proving model-agnosticism (Step 3).
- `seed_prompts.py` — load `app/prompts/seeds/*` into the `prompt_versions` table.
- `seed_tool_registry.py` — register built-in tools and their permission levels.
- `dev_up.sh` — bootstrap: run migrations, seed, and `docker compose up`.
