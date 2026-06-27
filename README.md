# ApexMind AI

A modular, **model-agnostic AI agent command center** — not a chatbot (though chat is
available). ApexMind plans complex goals, executes tools under a human-controlled
permission engine, runs untrusted code in a hardened sandbox, answers over your
documents with citations, and self-evaluates every answer.

> **Safety is load-bearing.** The permission engine, sandboxed tool worker,
> append-only audit log, and emergency stop are built *before* any "smart" agent
> behavior. Every model and tool call is audited. Level ≥3 actions pause for human
> approval; Level 5 actions are always refused.

## Architecture at a glance

| Layer | Tech | Notes |
|-------|------|-------|
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui + Recharts | chat, runs, memory, documents, benchmarks |
| Backend | Python + FastAPI (async, WebSocket) + Pydantic | orchestrator, router, safety, RAG, memory |
| DB | Postgres + pgvector | SQLite + Chroma fallback only if Postgres is unavailable |
| Queue | Redis | tool job queue, E-STOP flag, pub/sub |
| Tool worker | Separate Dockerized service | network-stripped, resource-limited Python executor |

### Model-agnostic by construction
Every model call goes through one internal `LLMInterface` (`generate()` / `embed()`)
and a `router()`. **No vendor SDK is imported outside `backend/app/router/adapters/`.**
Switching the default model is a `routing.yaml` / env change — never a code change.

## Quick start

```bash
cp .env.example .env          # fill in provider API keys you want to use
docker compose up             # api + tool-worker + postgres(pgvector) + redis
# Optional: include the frontend container
docker compose --profile full up
```

The frontend can also be run directly during development:

```bash
cd frontend && npm install && npm run dev
```

## Repository layout

See the directory tree in the project docs. Top level:

- `backend/` — FastAPI app (`app/`) with `orchestrator`, `router/adapters`,
  `agents/profiles`, `prompts`, `tools/impl`, `memory`, `rag`, `safety`,
  `benchmarks`, `audit`, `db`.
- `tool_worker/` — isolated, network-less code executor.
- `frontend/` — Next.js command center UI.
- `scripts/` — `prove_model_agnostic.py`, seeders, dev bootstrap.

## Build status

This repo is built in reviewable increments:

1. **Scaffold** — repo structure, docker-compose, .env.example ← _current_
2. DB migrations
3. LLM interface + router + Anthropic/OpenAI adapters
4. Audit logger (wired inside the adapter)
5. WebSocket chat (stream + persist) + minimal Next.js chat
6. Tool Manager + permission engine + sandbox + E-STOP
7. Orchestrator (plan → step loop under budget)
8. RAG-lite (cite chunks; "Unverified" when unsupported)
9. Memory-lite (project facts + viewer)
10. Self-eval (Critic scorecard)
11. Safety pre-screen (refuse harm, ignore injected instructions)
12. Benchmark runner (≥10 objective tests)

## Safety guarantees

The system will never: deploy itself, disable its own safety, hide errors, access
private data without consent, perform harmful cyber actions, manipulate the user, or
claim consciousness / guaranteed results. Self-improvement happens only via
propose → test → human-approve → version → rollback.
