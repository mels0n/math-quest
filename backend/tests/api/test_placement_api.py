"""Placement routes."""

import uuid

import httpx

from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, check
from mathquest.engine.placement import MAX_QUESTIONS
from mathquest.engine.types import Problem
from tests.conftest import SIGNUP_WORD, Api, ApiFactory

CSRF = {"X-Requested-With": "mathquest"}


class _SyncPool(CheckerPool):
    async def check(self, problem: Problem, latex: str) -> CheckResult:
        return check(problem, latex)


async def _signup(client: httpx.AsyncClient, nickname: str) -> None:
    r = await client.post(
        "/api/auth/signup",
        json={"signup_word": SIGNUP_WORD, "nickname": nickname, "pin": "1234"},
        headers=CSRF,
    )
    assert r.status_code == 200


async def _api(api: ApiFactory, nickname: str = "Placer", **overrides: object) -> Api:
    h = await api(**overrides)
    h.app.state.checker_pool = _SyncPool()
    await _signup(h.client, nickname)
    return h


async def _start(
    client: httpx.AsyncClient, body: dict[str, object] | None = None
) -> httpx.Response:
    return await client.post("/api/placement/start", json=body or {}, headers=CSRF)


async def _answer(client: httpx.AsyncClient, step: dict[str, object], latex: str) -> httpx.Response:
    problem = step["problem"]
    assert isinstance(problem, dict)
    return await client.post(
        "/api/placement/answer",
        json={
            "placement_id": step["placement_id"],
            "problem_id": problem["problem_id"],  # pyright: ignore[reportUnknownArgumentType]
            "latex": latex,
        },
        headers=CSRF,
    )


async def test_requires_login(api: ApiFactory) -> None:
    h = await api()
    assert (await _start(h.client)).status_code == 401


async def test_start_returns_a_problem_without_its_answer(api: ApiFactory) -> None:
    h = await _api(api)
    r = await _start(h.client, {"grade_hint": "K"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "done",
        "placement_id",
        "problem",
        "question",
        "max_questions",
        "retry",
    }
    assert body["done"] is False
    assert body["question"] == 1
    assert body["max_questions"] == MAX_QUESTIONS
    problem = body["problem"]
    assert problem["type"] == "problem"
    assert problem["skill_id"] == "add_within_10"
    assert problem["prompt"]
    assert problem["keypad"] == "numpad"
    assert problem["hint_levels"] == 0
    assert problem["dev_answer_latex"] is None
    assert problem["dev_answer_choice"] is None


async def test_a_grade_hint_must_be_k_to_8(api: ApiFactory) -> None:
    h = await _api(api)
    for bad in ("9", "A1", 3, "k", ""):
        r = await _start(h.client, {"grade_hint": bad})
        assert r.status_code == 422, bad
    assert (await _start(h.client, {"age": 7})).status_code == 422
    assert (await _start(h.client, {"grade_hint": None})).status_code == 200


async def test_a_whole_round_ends_with_the_outcome(api: ApiFactory) -> None:
    h = await _api(api, dev_expose_answers=True)
    step = (await _start(h.client)).json()
    body = step
    for _ in range(MAX_QUESTIONS):
        answer = step["problem"]["dev_answer_latex"]
        assert answer
        r = await _answer(h.client, step, answer)
        assert r.status_code == 200
        body = r.json()
        if body["done"]:
            break
        assert "verdict" not in body
        step = body
    assert body["done"] is True
    assert set(body) == {"done", "placement_id", "frontier", "provisional", "revealed_regions"}
    assert body["frontier"] == ["add_fractions_unlike"]
    assert "add_within_10" in body["provisional"]
    assert body["revealed_regions"][0] == {"id": "number_meadows", "name": "Number Meadows"}

    # The solved total is untouched; play can start straight on unlocked skills.
    me = (await h.client.get("/api/me")).json()
    assert me["total_solved"] == 0


async def test_unreadable_answers_are_asked_again(api: ApiFactory) -> None:
    h = await _api(api)
    step = (await _start(h.client)).json()
    r = await _answer(h.client, step, r"\frac{")
    assert r.status_code == 200
    body = r.json()
    assert body["retry"] == "unreadable"
    assert body["question"] == 1
    assert body["problem"]["problem_id"] == step["problem"]["problem_id"]


async def test_retake_starts_a_new_round(api: ApiFactory) -> None:
    h = await _api(api)
    first = (await _start(h.client)).json()
    second = (await _start(h.client, {"grade_hint": "5"})).json()
    assert second["placement_id"] != first["placement_id"]
    assert second["problem"]["skill_id"] == "add_fractions_unlike"
    r = await _answer(h.client, first, "1")
    assert r.status_code == 409
    assert r.json()["error"] == "placement_closed"


async def test_cannot_answer_someone_elses_round(api: ApiFactory) -> None:
    h = await _api(api, nickname="Owner")
    step = (await _start(h.client)).json()
    other = await api()
    other.app.state.checker_pool = _SyncPool()
    await _signup(other.client, "Intruder")
    r = await _answer(other.client, step, "1")
    assert r.status_code == 404


async def test_answer_body_is_validated(api: ApiFactory) -> None:
    h = await _api(api)
    step = (await _start(h.client)).json()
    base = {"placement_id": step["placement_id"], "problem_id": step["problem"]["problem_id"]}
    for body in (
        base,
        {**base, "latex": "1", "choice": 0},
        {**base, "latex": "1\x00"},
        {**base, "latex": "1" * 1001},
        {**base, "choice": -1},
        {**base, "latex": "1", "extra": True},
        {"placement_id": "nope", "problem_id": str(uuid.uuid4()), "latex": "1"},
    ):
        r = await h.client.post("/api/placement/answer", json=body, headers=CSRF)
        assert r.status_code == 422, body
    r = await h.client.post("/api/placement/answer", json={**base, "choice": 0}, headers=CSRF)
    assert r.status_code == 422
