# ApexMind AI — Build Progress & Handoff

> Living record of exactly where the build stands so any session can resume
> without re-deriving context. Update this at the end of every step.

**Branch:** `claude/apexmind-ai-mvp-dw318u`
**Last updated:** 2026-06-27, after Step 4.
**Latest commit:** Step 4 — append-only audit logger.

---

## Where we are right now

✅ **Step 1 — Scaffold** (commit `b481f9b`)
✅ **Step 2 — DB migrations** (commit `84509ca`)
✅ **Step 3 — LLM interface + router + adapters + prove script** (commit `f8f112e`)
✅ **Step 4 — Append-only audit logger, wired inside the adapter base**
⏭️ **NEXT: Step 5 — FastAPI WebSocket chat (stream + persist) + minimal Next.js chat screen**

Tree is clean; everything is pushed to `origin/claude/apexmind-ai-mvp-dw318u`.
Test suite: **17 passing** (10 router + 5 audit-pure + 2 audit-integration).

---

## Build order (12 steps) — status

| # | Step | Status |
|---|------|--------|
| 1 | Scaffold repo + docker-compose + .env.example | ✅ done |
| 2 | DB migrations (18 tables, pgvector, append-only audit) | ✅ done |
| 3 | LLM interface `generate()/embed()` + router + Anthropic/OpenAI adapters + prove script | ✅ done |
| 4 | Audit logger, called from inside the adapter (every model call logged) | ✅ done |
| 5 | FastAPI WebSocket chat (stream tokens + persist) + minimal Next.js chat | ⏭️ **next** |
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

## Step 3 — DONE (what shipped)

- `app/router/types.py` — `Message`, `LLMRequest`, `LLMResponse`, `Usage`, `EmbedRequest/Response` (no SDK).
- `app/router/adapters/base.py` — `BaseAdapter` ABC, the ONLY vendor boundary. `generate()/embed()` are
  **audited template methods**: they emit request/response/error events via `self._audit_hook`
  (no-op until Step 4 attaches the DB sink). `_generate/_embed` are the abstract provider methods.
- `app/router/adapters/{anthropic,openai,google}.py` — real adapters, **SDKs lazy-imported** inside methods
  (modules import fine without SDKs). `openai.py` also defines `OpenAICompatibleAdapter` (provider `local`).
- `app/router/router.py` — `Router` loads routing.yaml, resolves task_type→candidates, **skips providers
  with no adapter/key**, **falls back on error**; `build_adapters(settings, audit_hook)` builds only enabled
  providers. Errors: `NoAvailableProvider`, `AllCandidatesFailed`.
- `app/router/interface.py` — `LLMInterface.from_settings()`, `.generate()/.stream()/.embed()`; the app's sole entry point.
- `scripts/prove_model_agnostic.py` — prints a completion per configured provider (self-bootstraps sys.path).
- `backend/tests/test_router.py` — **10 tests pass**: candidate order, disabled-provider skip, first-success,
  fallback-on-error, all-fail detail, no-provider, default-model-is-config-only, audit hook fires on every
  call, audit records errors, stream fallback-before-first-token.

**Verified:** `pytest tests/ -q` → 10 passed; adapters import without SDKs; prove script no-keys path works.
**Note:** `local` provider is built when `LOCAL_OPENAI_BASE_URL` is set but has no routing.yaml entry yet
(local model IDs are deployment-specific) — add candidates there to route to it.

## Step 4 — DONE (what shipped)

- `app/audit/logger.py`:
  - `compute_entry_hash(...)` — pure SHA-256 over canonical row (`prev`, ts, actor, event_type,
    session_id, payload). Deterministic, unit-testable without a DB.
  - `verify_rows(rows)` / `AuditLogger.verify()` — recompute + check `prev_hash` links; returns
    `ChainCheck(ok, count, first_broken_id, reason)`.
  - `AuditLogger.append(...)` — serializes via `pg_advisory_xact_lock`, reads last `entry_hash`,
    writes a chained row. `.model_audit_hook()` returns the async hook for `BaseAdapter`.
    `.log_tool_call(...)` convenience ready for Step 6.
- `app/router/interface.py` — `from_settings(..., enable_default_audit=True)`: in production it
  auto-attaches an `AuditLogger` over `async_session_factory`, so the adapter base's audit seam writes
  real rows for EVERY model call. Tests pass `enable_default_audit=False` (no DB needed).
- Tests: `tests/test_audit.py` (5 pure) + `tests/test_audit_integration.py` (2 PG-backed, skip unless
  `APEX_TEST_DATABASE_URL` set).

**Verified against real Postgres:** a model call through BaseAdapter wrote `request`+`response` rows that
verify; chain tamper + broken-link both detected; **UPDATE/DELETE on audit_log rejected** by the trigger.
Full suite: 17 passed.

### How to run the PG integration tests
```bash
docker run -d --rm --name apex-pg-test -e POSTGRES_USER=apex -e POSTGRES_PASSWORD=apex \
  -e POSTGRES_DB=apexmind -p 5433:5432 pgvector/pgvector:pg16
cd backend
DATABASE_URL="postgresql+asyncpg://apex:apex@localhost:5433/apexmind" /tmp/apexvenv/bin/alembic upgrade head
APEX_TEST_DATABASE_URL="postgresql+asyncpg://apex:apex@localhost:5433/apexmind" \
  /tmp/apexvenv/bin/python -m pytest tests/ -q     # 17 passed
docker stop apex-pg-test
```

## Next step in detail (Step 5 — pick up here)

FastAPI WebSocket chat that streams tokens and persists, + a minimal Next.js chat screen:
1. `app/deps.py` — shared singletons (LLMInterface.from_settings(), session dep, audit logger).
2. Bootstrap helper to ensure a default user/project/session exist (dev convenience) OR accept
   session_id from the client; persist user/assistant messages to `messages`.
3. `app/main.py` — `GET /health` (exists) + `WS /ws/chat` that: receives a user message, persists it,
   streams assistant tokens via `LLMInterface.stream(task_type="fast"|"reasoning")`, persists the full
   assistant message at end. Treat model calls as audited automatically (Step 4).
4. REST helpers: create/list sessions + fetch message history (`app/api/` or routes in main).
5. Frontend: `frontend/src/lib/ws.ts` (WS client), `src/app/chat/page.tsx` (stream UI),
   `globals.css`/`layout.tsx`. Consume `NEXT_PUBLIC_API_BASE`.
6. Tests: a WS chat test using FastAPI TestClient with a fake LLMInterface (stub stream) asserting
   tokens stream and messages persist (use the PG test DB or a fake repo).

Acceptance for Step 5: chat screen streams tokens from the WS; user+assistant messages land in `messages`;
model calls show up in `audit_log`.
