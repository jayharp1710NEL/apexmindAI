"""Orchestrator control-flow tests with fakes (no DB, no network)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

from app.orchestrator.orchestrator import Orchestrator
from app.orchestrator.plan import Plan, PlanStep
from app.router.types import LLMResponse, Usage
from app.safety.estop import EStop
from app.tools.schema import ToolResult


def _settings(max_steps=12, max_seconds=300, max_cost=1.0):
    return SimpleNamespace(
        max_steps=max_steps, max_run_seconds=max_seconds, max_run_cost_usd=max_cost
    )


class FakeLLM:
    async def generate(self, task_type, *, prompt=None, system=None, messages=None,
                       max_tokens=1024, temperature=0.7, json_mode=False, stop=None,
                       model=None, provider=None):
        return LLMResponse(text=f"answer:{prompt or 'ctx'}", model=model or "fake-1",
                           provider=provider or "fake",
                           usage=Usage(input_tokens=5, output_tokens=7))

    async def stream(self, task_type, *, messages=None, prompt=None, system=None,
                     max_tokens=1024, temperature=0.7, json_mode=False) -> AsyncIterator[str]:
        for t in ["Fin", "al ", "answer"]:
            yield t


class FakeToolManager:
    def __init__(self):
        self.dispatched = []

    async def dispatch(self, name, args=None, *, session_id=None) -> ToolResult:
        self.dispatched.append((name, args))
        if name == "code_exec":
            return ToolResult(tool_name="code_exec", level=2, status="ok",
                              stdout="sandbox-output-42\n")
        return ToolResult(tool_name=name, level=1, status="ok",
                          result={"content": "web data"})


def _orch(estop, settings, planner):
    return Orchestrator(llm=FakeLLM(), tool_manager=FakeToolManager(), estop=estop,
                        settings=settings, session_factory=None, planner=planner)


def _mk_emit(events):
    async def emit(ev):
        events.append(ev)
    return emit


async def _collect(orch, goal="do a thing"):
    events = []
    res = await orch.run(goal=goal, session_id=None, emit=_mk_emit(events))
    return events, res


async def test_runs_plan_streams_final_and_shows_sandbox_stdout():
    plan = Plan(goal="g", steps=[
        PlanStep(id=1, description="think", agent="none", tool="none"),
        PlanStep(id=2, description="run code", tool="code_exec", tool_level=2,
                 tool_input="print('x')"),
    ], estimated_steps=2)

    async def planner(llm, goal, session_factory=None):
        return plan

    events, res = await _collect(_orch(EStop(), _settings(), planner))
    types = [e["type"] for e in events]
    assert types[0] == "plan"
    assert "step_start" in types and "step_result" in types
    assert "token" in types and types[-1] == "done"
    # sandbox stdout surfaced in a step_result
    step_results = [e for e in events if e["type"] == "step_result"]
    assert any("sandbox-output-42" in (e.get("stdout") or "") for e in step_results)
    assert res["status"] == "completed"
    assert "".join(e["content"] for e in events if e["type"] == "token") == "Final answer"


async def test_estop_halts_between_steps():
    # E-STOP reads False for step 1, then True for step 2 -> halts before step 2.
    class TogglingEstop(EStop):
        def __init__(self):
            super().__init__()
            self.n = 0

        async def is_engaged(self):
            self.n += 1
            return self.n > 1

    # step 2 depends on step 1 -> separate waves -> E-STOP checked between them
    plan = Plan(goal="g", steps=[
        PlanStep(id=1, description="a", tool="none"),
        PlanStep(id=2, description="b", tool="none", depends_on=[1]),
    ])

    async def planner(llm, goal, session_factory=None):
        return plan

    tm = FakeToolManager()
    orch = Orchestrator(llm=FakeLLM(), tool_manager=tm, estop=TogglingEstop(),
                        settings=_settings(), session_factory=None, planner=planner)
    events = []
    res = await orch.run(goal="g", session_id=None, emit=_mk_emit(events))
    starts = [e for e in events if e["type"] == "step_start"]
    assert len(starts) == 1            # only step 1 started
    assert any(e["type"] == "halted" for e in events)
    assert res["status"] == "stopped"
    assert not any(e["type"] == "token" for e in events)  # no final synthesis


async def test_independent_steps_run_in_parallel():
    plan = Plan(goal="g", steps=[
        PlanStep(id=1, description="a", tool="none"),
        PlanStep(id=2, description="b", tool="none"),
        PlanStep(id=3, description="c", tool="none"),
    ])

    async def planner(llm, goal, session_factory=None):
        return plan

    events, res = await _collect(_orch(EStop(), _settings(), planner))
    # all three with no deps -> one parallel wave
    assert any(e["type"] == "parallel" and len(e["ids"]) == 3 for e in events)
    assert len([e for e in events if e["type"] == "step_result"]) == 3
    assert res["status"] == "completed"


async def test_budget_caps_steps():
    # chain the steps so each is its own wave -> budget caps after the first
    plan = Plan(goal="g", steps=[
        PlanStep(id=1, description="a", tool="none"),
        PlanStep(id=2, description="b", tool="none", depends_on=[1]),
        PlanStep(id=3, description="c", tool="none", depends_on=[2]),
    ])

    async def planner(llm, goal, session_factory=None):
        return plan

    orch = _orch(EStop(), _settings(max_steps=1), planner)
    events = []
    res = await orch.run(goal="g", session_id=None, emit=_mk_emit(events))
    starts = [e for e in events if e["type"] == "step_start"]
    assert len(starts) == 1
    assert any(e["type"] == "halted" and "budget" in e["reason"] for e in events)
    assert res["status"] == "stopped"
