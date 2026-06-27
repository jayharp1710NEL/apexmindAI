"""Planner tests: strict-JSON extraction + degradation to a single-step plan."""

from __future__ import annotations

from app.orchestrator.planner import extract_json, generate_plan
from app.router.types import LLMResponse, Usage


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fence_and_prose():
    text = 'Here is the plan:\n```json\n{"goal": "g", "steps": []}\n```\nthanks'
    assert extract_json(text) == {"goal": "g", "steps": []}


class _LLM:
    def __init__(self, text):
        self._text = text

    async def generate(self, task_type, **kw):
        return LLMResponse(text=self._text, model="m", provider="fake",
                           usage=Usage())


async def test_generate_plan_parses_valid_json():
    payload = (
        '{"goal":"build x","steps":['
        '{"id":1,"description":"research","agent":"research","tool":"web_search",'
        '"tool_level":1,"tool_input":"x","expected_output":"facts"}],'
        '"estimated_steps":1}'
    )
    plan = await generate_plan(_LLM(payload), "build x")
    assert plan.goal == "build x"
    assert len(plan.steps) == 1
    assert plan.steps[0].tool == "web_search"


async def test_generate_plan_degrades_on_garbage():
    plan = await generate_plan(_LLM("not json at all"), "simple goal")
    assert len(plan.steps) == 1            # single-step fallback
    assert plan.steps[0].description == "simple goal"
