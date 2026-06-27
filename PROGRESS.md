# ApexMind AI — Build Progress & Handoff

> Living record of exactly where the build stands so any session can resume
> without re-deriving context. Update this at the end of every step.

**Branch:** `claude/apexmind-ai-mvp-dw318u`
**Last updated:** 2026-06-27, after Step 11.
**Latest commit:** Step 11 — safety pre-screen.

---

## Where we are right now

✅ **Step 1–6** (commits `b481f9b`, `84509ca`, `f8f112e`, `be958a0`, `18f9aca`, Step 6)
✅ **Step 7 — Orchestrator + web tools**
✅ **Step 8 — RAG-lite (cite [n]; "Unverified")**
✅ **Step 9 — Memory-lite**
✅ **Step 10 — Self-eval Critic scorecard**
✅ **Step 11 — Safety pre-screen: refuse harm, allow benign look-alikes, flag injected instructions**
⏭️ **NEXT: Step 12 — Benchmark runner (≥10 objective tests) + "Run suite" results view**

Tree is clean; everything is pushed to `origin/claude/apexmind-ai-mvp-dw318u`.
Test suite: **82 passing** (75 backend + 7 tool_worker sandbox).
Frontend: `npm run build` succeeds (/, /chat, /runs, /documents, /memory).

---

## Build order (12 steps) — status

| # | Step | Status |
|---|------|--------|
| 1 | Scaffold repo + docker-compose + .env.example | ✅ done |
| 2 | DB migrations (18 tables, pgvector, append-only audit) | ✅ done |
| 3 | LLM interface `generate()/embed()` + router + Anthropic/OpenAI adapters + prove script | ✅ done |
| 4 | Audit logger, called from inside the adapter (every model call logged) | ✅ done |
| 5 | FastAPI WebSocket chat (stream tokens + persist) + minimal Next.js chat | ✅ done |
| 6 | Tool Manager + permission engine (L0–5) + Dockerized code_exec (L2) + E-STOP + L≥3 approval | ✅ done |
| 7 | Orchestrator: JSON plan → sequential steps under step/cost/time budget, E-STOP between steps | ✅ done |
| 8 | RAG-lite: upload→chunk→embed→pgvector→top-k→cite [n]; "Unverified" when unsupported | ✅ done |
| 9 | Memory-lite: project_facts persist + inject + viewer (list/delete) | ✅ done |
| 10 | Self-eval: Critic JSON {issues, hallucination_risk, confidence}; revise once if high; scorecard | ✅ done |
| 11 | Safety pre-screen on requests + tool calls; ignore+flag injected instructions | ✅ done |
| 12 | Benchmark runner ≥10 objective tests + "Run suite" view | ⏭️ **next** |

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

## Step 5 — DONE (what shipped)

Backend (new `app/chat/` package + `app/deps.py`):
- `app/deps.py` — read `llm` / `session_factory` off `app.state` (injectable in tests).
- `app/chat/schemas.py` — REST + WS payloads (UserMessageIn; Start/Token/Done/Error events).
- `app/chat/repository.py` — users/projects/sessions/messages persistence; `get_or_create_default_context`
  (dev user `dev@apexmind.local` + `Default` project so the UI needs no auth flow yet).
- `app/chat/service.py` — `handle_turn`: persist user msg → load history → `llm.stream(task_type)` emitting
  token events → persist full assistant msg → `done`. Errors surface as an `error` event (never hidden).
- `app/chat/routes.py` — REST `POST/GET /api/sessions`, `GET /api/sessions/{id}/messages`; `WS /ws/chat/{session_id}`.
- `app/main.py` — `create_app(llm=None, session_factory=None)`: CORS, wires `app.state`, mounts chat router.
  Model calls auto-audited via Step 4 (default interface attaches the audit hook).

Frontend (Next.js):
- `src/lib/api.ts` (REST + base URLs), `src/lib/ws.ts` (`ChatSocket`), `src/lib/utils.ts` (`cn`).
- `src/app/layout.tsx`, `globals.css` (dark theme), `page.tsx` (landing), `chat/page.tsx`
  (streaming chat UI: live token append, connection status, disabled-while-streaming).

**Verified:** WS test (real PG + fake streaming LLM) — tokens stream in order, user+assistant persist;
unknown-session → error event. Full backend suite **19 passed**. Frontend `tsc --noEmit` clean and
`next build` succeeds. Next bumped to patched `^14.2.35` (CVE in 14.2.5).

WS protocol: client → `{type:"user_message", content, task_type}`; server → `{type:"start"}`,
`{type:"token", content}`…, `{type:"done", message_id}` or `{type:"error", detail}`.

## Step 6 — DONE (what shipped)

- `app/safety/permission_engine.py` — pure `PermissionEngine.decide(level, estop_engaged)` →
  ALLOW (0–2) / NEEDS_APPROVAL (3–4) / DENY (5, invalid, estop, or above `max_level`). `max_level`
  clamped to ≤4 so L5 is always refused.
- `app/safety/estop.py` — `EStop` Redis-backed global switch with graceful in-memory fallback
  (`from_settings` guards the redis import). engage/clear/is_engaged.
- `app/safety/approvals.py` — `ApprovalRegistry`: request → asyncio.Event wait (timeout = auto-DENY) →
  resolve(approved). `pending()` for the UI.
- `app/tools/{schema,registry,manager}.py` — `ToolManager.dispatch` runs the fixed safety sequence:
  level lookup → E-STOP → permission decision → (approval, timeout=deny) → **re-check E-STOP after
  approval** → execute → audit (`log_tool_call`) + persist `tool_results`. Tool body only reached on ALLOW.
- `app/tools/impl/code_exec.py` — L2; `make_local_code_exec` (in-process sandbox, dev/tests) +
  `make_redis_code_exec` (enqueue to worker, await result).
- `tool_worker/executor.py` — `run_code`: subprocess, socket-disabled preamble, RLIMIT_CPU/AS/FSIZE,
  wall-timeout kill, clean env (no host secrets), output cap. `tool_worker/worker.py` — Redis job loop.
- `app/safety/routes.py` + `main.py` wiring — `/api/safety/estop[/engage|/clear]`,
  `/api/safety/approvals[/{id}/resolve]`; `app.state` now has `estop`, `approvals`, `tool_manager`.

**Verified:** 47 tests pass. Headline acceptance proven: **Level-3 action does NOT execute without
approval** (spy never runs); also L2 auto-runs, L5 refused, E-STOP halts (incl. engaged-during-approval),
approval-then-run works; sandbox runs real code with real stdout, blocks network, enforces timeout, caps
output; e2e ToolManager→sandbox returns real output.

## Step 7 — DONE (what shipped)

- `app/orchestrator/plan.py` — `Plan`/`PlanStep` schema (+ `tool_input`, `Plan.single`).
- `app/orchestrator/budget.py` — `Budget` (steps/time hard caps; cost estimated via price table).
- `app/prompts/registry.py` — `get_active_prompt` (DB `prompt_versions` if seeded, else seed file).
- `app/orchestrator/planner.py` — `generate_plan` (structured_json + json_mode), robust `extract_json`,
  degrades to single-step on bad output.
- `app/orchestrator/orchestrator.py` — `Orchestrator.run`: persist run → plan → loop steps with
  **E-STOP check before every step** + budget check → execute (tool steps via ToolManager so
  permission/approval/audit apply; code_exec generates code if `tool_input` empty) → persist steps →
  stream final synthesis (treats step outputs as untrusted DATA) → persist final + finish run. Emits
  plan/step_start/step_result/token/done/halted/error events.
- `app/tools/impl/web_fetch.py` + `web_search.py` (**L1**) — httpx fetch (HTML→text) + keyless DuckDuckGo
  search; both return `untrusted: true` + `injection_flags`. Registered in the ToolManager.
- `app/orchestrator/routes.py` + `main.py` — `WS /ws/run/{session_id}`; `app.state.orchestrator`.
- Frontend `src/app/runs/page.tsx` + `RunSocket` — shows plan, per-step status, **real sandbox stdout**,
  streamed answer, halted/cost status.

**Verified:** 56 tests pass (49 backend + 7 sandbox). Orchestrator tests prove: plan runs and streams a
final answer with **real sandbox stdout surfaced**; **E-STOP halts between steps** (step 2 never starts);
**budget caps** the run; planner parses strict JSON and degrades gracefully. Frontend builds (/, /chat, /runs).

## Next step in detail (Step 8 — pick up here)

RAG-lite with citations:
1. `app/rag/chunker.py` — split text into ~`CHUNK_SIZE_TOKENS` chunks w/ overlap (token-ish by words).
2. `app/rag/ingest.py` — accept an uploaded file (text/markdown/PDF-as-text for MVP), persist `documents`,
   chunk → `llm.embed()` → store `doc_chunks` with embedding (pgvector).
3. `app/rag/retrieve.py` — embed the query, pgvector top-k (cosine `<=>`) over a project's chunks; return
   chunks with ids + scores.
4. `app/rag/answer.py` — build a grounded prompt: answer ONLY from retrieved chunks, cite as `[n]` mapping
   to chunk ids; if no chunk supports a claim, output **"Unverified"**. Strict instruction + post-check.
5. Routes: `POST /api/documents` (upload+ingest), `GET /api/documents`, `POST /api/rag/query`
   (returns answer + citations). Frontend `src/app/documents/page.tsx` (upload + Q&A with citations).
6. Tests (PG + pgvector, fake embeddings): ingest stores chunks w/ vectors; retrieve returns the relevant
   chunk; answer cites `[n]`→chunk id; unsupported query yields "Unverified".

Acceptance for Step 8: document Q&A cites chunk ids, and says "Unverified" when no chunk supports the claim.

## (historical) Step 7 plan — pick up here

Orchestrator + web tools end-to-end:
1. `app/tools/impl/web_search.py` + `web_fetch.py` (**L1**): use WebFetch/an HTTP client; return results as
   untrusted DATA (wrap content, strip/flag any embedded instructions — full prescreen is Step 11).
   Register them in ToolManager impls.
2. `app/orchestrator/budget.py` — track steps/cost/time vs `MAX_STEPS`/`MAX_RUN_SECONDS`/`MAX_RUN_COST_USD`.
3. `app/orchestrator/planner.py` — call the LLM (task_type `structured_json`) with the orchestrator prompt
   to produce a strict-JSON plan; parse + validate against a Pydantic Plan schema.
4. `app/orchestrator/orchestrator.py` — for a complex goal: persist a `runs` row, generate plan, execute
   `steps` sequentially via ToolManager, **check E-STOP between steps**, enforce budget, persist each `step`,
   stream progress events. Simple goals can skip planning (single answer step).
5. WS/REST surface: a way to start an orchestrated run and stream plan + step + sandbox-stdout events to the
   UI; show real sandbox stdout in the Runs view (`frontend/src/app/runs/page.tsx`).
6. Tests: planner parses strict JSON (fake LLM); orchestrator stops on E-STOP between steps; budget caps the
   run; a code_exec step shows real stdout.

Acceptance for Step 7: complex goal → plan-based streamed answer; steps run under budget; E-STOP halts a run
between steps; real sandbox stdout surfaced.

## (historical) Step 6 plan — pick up here

Tool Manager + permission engine + sandboxed code_exec + E-STOP + approval gate:
1. `app/safety/estop.py` — global E-STOP backed by Redis key `settings.estop_key` (engage/clear/is_engaged);
   in-memory fallback if Redis absent (for tests).
2. `app/safety/permission_engine.py` — Levels 0–5. Decision for a (tool, level): L0–2 auto-allow (subject to
   E-STOP), **L3–4 require explicit human approval**, **L5 always refused**. Returns allow/deny/needs_approval.
3. `app/safety/approvals.py` — approval registry: create pending approval (id), `await` an asyncio.Event with
   timeout (`APPROVAL_TIMEOUT_SECONDS`) → auto-deny on timeout; `resolve(id, approved)` from an API route.
4. `app/tools/schema.py` (ToolCall/ToolResult), `app/tools/registry.py` (name→level), `app/tools/manager.py`
   (dispatch: prescreen via permission engine → E-STOP check → run impl → log via `AuditLogger.log_tool_call`
   + persist `tool_results`).
5. `app/tools/impl/code_exec.py` (**L2**) — enqueue job to Redis for the tool_worker; await result.
6. `tool_worker/worker.py` + `executor.py` — pull job, run untrusted code in a subprocess with **no network**,
   rlimits (CPU/mem via `resource`), timeout, output cap; return stdout/stderr/returncode.
7. **Unit test proving a Level-3 action does NOT execute without approval** (acceptance), plus E-STOP halts,
   L5 refused, L2 allowed.

Acceptance for Step 6: L3 pauses for approval and won't run unapproved; code runs sandboxed (no net) with real
stdout; E-STOP flag halts; every tool call audited + in `tool_results`.
