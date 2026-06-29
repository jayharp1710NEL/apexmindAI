"""In-memory run-job store so runs can be started via REST and polled.

POST /api/runs starts an orchestrated run in the background and returns a job id;
GET /api/runs/{id} returns its live status, plan, per-step results, and final answer.
(Single-process store — fine for the local app; swap for Redis to scale out.)
"""

from __future__ import annotations

import uuid
from typing import Any


class RunJob:
    def __init__(self, goal: str, session_id: str) -> None:
        self.id = str(uuid.uuid4())
        self.goal = goal
        self.session_id = session_id
        self.status = "running"           # running|completed|stopped|refused|error
        self.run_id: str | None = None
        self.plan: dict | None = None
        self.steps: dict[int, dict] = {}
        self.final: str = ""
        self.error: str | None = None

    def apply(self, ev: dict[str, Any]) -> None:
        t = ev.get("type")
        if t == "plan":
            self.plan = ev.get("plan")
            self.run_id = ev.get("run_id")
        elif t == "step_start":
            self.steps[ev["id"]] = {
                "id": ev["id"], "description": ev.get("description"),
                "agent": ev.get("agent"), "tool": ev.get("tool"), "status": "running",
            }
        elif t == "step_result":
            self.steps.setdefault(ev["id"], {"id": ev["id"]}).update({
                "status": ev.get("status"), "stdout": ev.get("stdout"),
                "model": ev.get("model"), "summary": ev.get("summary"),
            })
        elif t == "token":
            self.final += ev.get("content", "")
        elif t == "refusal":
            self.status = "refused"
            self.final = ev.get("content", "")
        elif t == "halted":
            self.status = "stopped"
        elif t == "done":
            self.status = "completed"
        elif t == "error":
            self.error = ev.get("detail")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "status": self.status, "run_id": self.run_id,
            "goal": self.goal, "session_id": self.session_id,
            "plan": self.plan,
            "steps": [self.steps[k] for k in sorted(self.steps)],
            "final": self.final, "error": self.error,
        }


class RunJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, RunJob] = {}

    def create(self, goal: str, session_id: str) -> RunJob:
        job = RunJob(goal, session_id)
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> RunJob | None:
        return self._jobs.get(job_id)
