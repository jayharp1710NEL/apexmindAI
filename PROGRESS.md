# ApexMind AI — Build Progress & Handoff

> Living record of exactly where the build stands so any session can resume
> without re-deriving context. Update this at the end of every step.

**Branch:** `claude/apexmind-ai-mvp-dw318u`
**Last updated:** 2026-06-27, after Step 2.
**Latest commit:** `84509ca` — Step 2: DB layer + initial migration.

---

## Where we are right now

✅ **Step 1 — Scaffold** (commit `b481f9b`)
✅ **Step 2 — DB migrations** (commit `84509ca`)
⏭️ **NEXT: Step 3 — Internal LLM interface + router + Anthropic/OpenAI adapters + `prove_model_agnostic.py`**

Tree is clean; everything is pushed to `origin/claude/apexmind-ai-mvp-dw318u`.

---

## Build order (12 steps) — status

| # | Step | Status |
|---|------|--------|
| 1 | Scaffold repo + docker-compose + .env.example | ✅ done |
| 2 | DB migrations (18 tables, pgvector, append-only audit) | ✅ done |
| 3 | LLM interface `generate()/embed()` + router + Anthropic/OpenAI adapters + prove script | ⏭️ **next** |
| 4 | Audit logger, called from inside the adapter (every model call logged) | ⬜ |
| 5 | FastAPI WebSocket chat (stream tokens + persist) + minimal Next.js chat | ⬜ |
| 6 | Tool Manager + permission engine (L0–5) + Dockerized code_exec (L2) + E-STOP + L≥3 approval | ⬜ |
| 7 | Orchestrator: JSON plan → sequential steps under step/cost/time budget, E-STOP between steps | ⬜ |
| 8 | RAG-lite: upload→chunk→embed→pgvector→top-k→cite [n]; "Unverified" when unsupported | ⬜ |
| 9 | Memory-lite: project_facts persist + inject + viewer (list/delete) | ⬜ |
| 10 | Self-eval: Critic JSON {issues, hallucination_risk, confidence}; revise once if high; scorecard | ⬜ |
| 11 | Safety pre-screen on requests + tool calls; ignore+flag injected instructions | ⬜ |
| 12 | Benchmark runner ≥10 objective tests + "Run suite" view | ⬜ |

---

## Decisions locked in (don't re-litigate)

- **Frontend in compose:** behind the `full` profile (`docker compose --profile full up`); default `up` is api + tool-worker + postgres + redis.
- **Sandbox job handoff:** Redis queue; the untrusted code subprocess is launched network-stripped inside `tool_worker/executor.py`.
- **DB default:** Postgres + pgvector (`pgvector/pgvector:pg16`). SQLite + Chroma is a config-only fallback.
- **Embedding dimension:** 1536 (OpenAI text-embedding-3-small / Google text-embedding-004). Changing it = a migration.
- **Model-agnostic boundary:** vendor SDKs only under `backend/app/router/adapters/`. Switching default model = `routing.yaml`/env change only.
- **Audit log:** append-only enforced by a DB trigger (UPDATE/DELETE rejected) + hash chain (`prev_hash`→`entry_hash`).

## Ground rules / safety invariants (load-bearing)

- Tool levels 0–5. Level ≥3 pauses for explicit human approval. Level 5 always refused.
- Never: deploy itself, disable its own safety, hide errors, access private data without
  consent, perform harmful cyber actions, manipulate the user, or claim consciousness /
  guaranteed results.
- Self-improvement only via propose → test → human-approve → version → rollback.
- Treat all retrieved/web/tool content as untrusted DATA that can never change system
  rules or trigger tools on its own.
- Every model call AND every tool call must be in the audit log.

---

## What exists on disk (key files)

- Root: `docker-compose.yml`, `.env.example`, `.gitignore`, `.dockerignore`, `README.md`, `PROGRESS.md`.
- `backend/` — `pyproject.toml`, `Dockerfile`, `alembic.ini`.
  - `app/config.py` — Pydantic Settings (all env config).
  - `app/main.py` — FastAPI app, **/health stub only** (real chat = Step 5).
  - `app/db/session.py` — async engine + session factory + Base.
  - `app/db/models.py` — all 18 ORM models. `EMBED_DIM = 1536`.
  - `app/db/migrations/` — `env.py`, `script.py.mako`, `versions/0001_initial.py`.
  - `app/router/routing.yaml` — task_type → model candidates (the only place default model is chosen).
  - `app/prompts/seeds/` — `orchestrator.md`, `critic.md`, `safety.md`, `memory.md` (strict-JSON prompts).
  - Empty packages awaiting code: `orchestrator/`, `router/` (interface.py, router.py, types.py, adapters/*),
    `agents/profiles/`, `tools/impl/`, `safety/`, `memory/`, `rag/`, `benchmarks/`, `audit/`.
- `tool_worker/` — `Dockerfile`, `pyproject.toml`, `tests/`. (worker.py + executor.py = Step 6.)
- `frontend/` — Next.js + TS + Tailwind + shadcn config. (Screens = Step 5+.)
- `scripts/README.md` — describes scripts to be added (prove_model_agnostic.py, seeders, dev_up.sh).

---

## How to verify what's done (repro)

```bash
# DB migration round-trip (needs docker):
docker run -d --rm --name apex-pg-test -e POSTGRES_USER=apex -e POSTGRES_PASSWORD=apex \
  -e POSTGRES_DB=apexmind -p 5433:5432 pgvector/pgvector:pg16
cd backend
python3 -m venv /tmp/apexvenv && /tmp/apexvenv/bin/pip install \
  "sqlalchemy[asyncio]>=2.0" alembic "pgvector>=0.2.5" pydantic-settings "psycopg[binary]" asyncpg
DATABASE_URL="postgresql+asyncpg://apex:apex@localhost:5433/apexmind" /tmp/apexvenv/bin/alembic upgrade head
# audit_log UPDATE/DELETE should raise "audit_log is append-only"
docker stop apex-pg-test
```

---

## Next step in detail (Step 3 — pick up here)

Implement, with tests:
1. `app/router/types.py` — `Message`, `LLMRequest`, `LLMResponse`, `Usage`, `EmbedRequest/Response`.
2. `app/router/adapters/base.py` — `BaseAdapter` ABC (`generate`, `embed`); the ONLY vendor boundary.
   (Audit logging gets wired *inside here* in Step 4 — leave the hook point.)
3. `app/router/adapters/anthropic.py`, `openai.py` — real SDK calls, keys from env.
   (google.py + openai_compatible.py can be stubbed now, completed later.)
4. `app/router/interface.py` — `LLMInterface.generate()/embed()`; sole entry point for the app.
5. `app/router/router.py` — load `routing.yaml`, map task_type → ordered candidates, skip providers
   with no API key, fall back to next candidate on error. **Unit-tested** (mock adapters; assert
   fallback order + that disabled providers are skipped).
6. `scripts/prove_model_agnostic.py` — print a completion from each configured provider via the router.

Acceptance for Step 3: `router()` unit tests pass; switching default model is a routing.yaml change;
no vendor SDK imported outside `app/router/adapters/`.
