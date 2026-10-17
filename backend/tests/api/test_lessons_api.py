"""Lesson routes and the lesson step of play: lesson first, seen per player, replay, try-it."""

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, check
from mathquest.engine.types import Problem
from tests.conftest import SIGNUP_WORD, Api, ApiFactory

CSRF = {"X-Requested-With": "mathquest"}
LESSON_CLIENT = {**CSRF, "X-MathQuest-Client": "2"}
"""What a client that can show lessons sends with `next`."""
FIRST_SKILL = "add_within_10"
"""The skill a new player starts on: it has a lesson."""
NO_LESSON = "equivalent_fractions"


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


async def _api(api: ApiFactory, nickname: str = "Learner", **overrides: object) -> Api:
    h = await api(**overrides)
    h.app.state.checker_pool = _SyncPool()
    await _signup(h.client, nickname)
    return h


async def _next(
    client: httpx.AsyncClient, session_id: str, headers: dict[str, str] = LESSON_CLIENT
) -> dict[str, object]:
    r = await client.post(f"/api/play/sessions/{session_id}/next", headers=headers)
    assert r.status_code == 200
    return r.json()


async def _session(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/play/sessions", json={"mode": "adventure"}, headers=CSRF)
    assert r.status_code == 200
    return r.json()["session_id"]


async def _seen(client: httpx.AsyncClient, skill_id: str) -> httpx.Response:
    return await client.post(f"/api/lessons/{skill_id}/seen", headers=CSRF)


async def test_first_encounter_is_a_lesson_then_the_problem(api: ApiFactory) -> None:
    h = await _api(api)
    session_id = await _session(h.client)

    first = await _next(h.client, session_id)
    assert first == {"type": "lesson", "skill_id": FIRST_SKILL, "skill_name": "Add to 10"}
    # Asking again without marking it seen offers the lesson again; no problem is issued.
    assert await _next(h.client, session_id) == first

    assert (await _seen(h.client, FIRST_SKILL)).json() == {"skill_id": FIRST_SKILL, "seen": True}
    problem = await _next(h.client, session_id)
    assert problem["type"] == "problem"
    assert problem["skill_id"] == FIRST_SKILL

    # A new session does not show the lesson again.
    again = await _next(h.client, await _session(h.client))
    assert again["type"] == "problem"


async def test_a_client_that_cannot_show_lessons_gets_problems(api: ApiFactory) -> None:
    h = await _api(api)
    session_id = await _session(h.client)
    for headers in (CSRF, {**CSRF, "X-MathQuest-Client": "1"}, {**CSRF, "X-MathQuest-Client": "x"}):
        problem = await _next(h.client, session_id, headers)
        assert problem["type"] == "problem" and problem["skill_id"] == FIRST_SKILL
    # The lesson is still waiting for a client that can show it.
    assert (await _next(h.client, session_id))["type"] == "lesson"


async def test_seen_is_per_player_and_idempotent(api: ApiFactory) -> None:
    h = await _api(api, "First")
    assert (await _seen(h.client, FIRST_SKILL)).status_code == 200
    assert (await _seen(h.client, FIRST_SKILL)).status_code == 200
    assert (await _next(h.client, await _session(h.client)))["type"] == "problem"

    other = await api()
    other.app.state.checker_pool = _SyncPool()
    await _signup(other.client, "Second")
    assert (await _next(other.client, await _session(other.client)))["type"] == "lesson"


async def test_lesson_replays_whether_seen_or_not(api: ApiFactory) -> None:
    h = await _api(api)
    before = await h.client.get(f"/api/lessons/{FIRST_SKILL}")
    assert before.status_code == 200
    await _seen(h.client, FIRST_SKILL)
    after = await h.client.get(f"/api/lessons/{FIRST_SKILL}")
    assert after.status_code == 200
    assert after.json() == before.json()

    body = after.json()
    assert set(body) == {"skill_id", "skill_name", "screens", "worked_example", "try_it"}
    assert 2 <= len(body["screens"]) <= 4
    for screen in body["screens"]:
        assert set(screen) == {"title", "body", "visual"}
        assert screen["body"]
    visuals = [s["visual"] for s in body["screens"] if s["visual"] is not None]
    assert {"kind": "number_line", "params": {
        "min": 0, "max": 12, "start": 8, "jumps": [1, 1, 1], "end": 11,
    }} in visuals  # fmt: skip
    assert body["worked_example"]["prompt"] == [{"kind": "math", "value": "7 + 5 = ?"}]
    assert len(body["worked_example"]["steps"]) == 4
    assert body["try_it"] == {"tier": 0}


async def test_missing_lessons_are_404(api: ApiFactory) -> None:
    h = await _api(api)
    assert (await h.client.get(f"/api/lessons/{NO_LESSON}")).status_code == 404
    assert (await h.client.get("/api/lessons/no_such_skill")).status_code == 404
    assert (await h.client.get("/api/lessons/Bad-Id")).status_code == 422
    assert (await _seen(h.client, NO_LESSON)).status_code == 404
    r = await h.client.post(f"/api/lessons/{NO_LESSON}/try", headers=CSRF)
    assert r.status_code == 404


async def test_lessons_need_a_player(api: ApiFactory) -> None:
    h = await api()
    assert (await h.client.get(f"/api/lessons/{FIRST_SKILL}")).status_code == 401
    assert (await _seen(h.client, FIRST_SKILL)).status_code == 401


async def _try(client: httpx.AsyncClient) -> dict[str, object]:
    r = await client.post(f"/api/lessons/{FIRST_SKILL}/try", headers=CSRF)
    assert r.status_code == 200
    return r.json()


async def _answer_try(client: httpx.AsyncClient, try_id: object, latex: str) -> httpx.Response:
    return await client.post(
        f"/api/lessons/tries/{try_id}/answer", json={"latex": latex}, headers=CSRF
    )


async def test_try_it_is_checked_but_changes_nothing(api: ApiFactory, db: AsyncSession) -> None:
    h = await _api(api, dev_expose_answers=True)
    problem = await _try(h.client)
    assert set(problem) == {
        "try_id", "skill_id", "skill_name", "prompt", "keypad", "dev_answer_latex",
    }  # fmt: skip
    assert problem["skill_id"] == FIRST_SKILL
    answer = str(problem["dev_answer_latex"])
    wrong = str(int(answer) + 3)

    missed = (await _answer_try(h.client, problem["try_id"], wrong)).json()
    assert missed["verdict"] == "incorrect"
    # Feedback like play's; a try-it has no hints, so the generic line is "retry".
    assert missed["feedback"]["kind"] == "retry"
    assert answer not in [p["value"] for p in missed["feedback"]["text"]]
    assert missed["solved"] is False
    assert missed["attempts_left"] == 2
    assert missed["answer_latex"] is None

    solved = (await _answer_try(h.client, problem["try_id"], answer)).json()
    assert solved == {
        "verdict": "correct", "misconception": None, "feedback": None, "solved": True,
        "attempts_left": 2, "answer_latex": answer,
    }  # fmt: skip
    # Answering again returns the stored outcome.
    assert (await _answer_try(h.client, problem["try_id"], wrong)).json()["solved"] is True

    me = (await h.client.get("/api/me")).json()
    assert me["total_solved"] == 0
    count = await db.scalar(text("SELECT count(*) FROM skill_mastery"))
    assert count == 0
    issued = await db.scalar(text("SELECT count(*) FROM problem_instances"))
    assert issued == 0


async def test_a_try_it_mistake_gets_its_feedback(api: ApiFactory) -> None:
    h = await _api(api, dev_expose_answers=True)
    problem = await _try(h.client)
    catalog = h.app.state.catalog
    prompt = str(problem["prompt"][0]["value"])  # type: ignore[index]
    a, b = (int(n) for n in prompt.split("=")[0].split("+"))
    if a == b:
        return  # the subtracted mistake would read 0; covered by other seeds
    r = (await _answer_try(h.client, problem["try_id"], str(abs(a - b)))).json()
    assert r["misconception"] == "subtracted_instead"
    assert r["feedback"]["kind"] == "misconception"
    assert r["feedback"]["text"][0]["value"].startswith("It looks like you took away")
    assert FIRST_SKILL in catalog.pack.explanations


async def test_asking_for_the_try_it_again_reuses_the_open_one(
    api: ApiFactory, db: AsyncSession
) -> None:
    h = await _api(api, dev_expose_answers=True)
    first = await _try(h.client)
    assert (await _try(h.client)) == first
    rows = await db.scalar(text("SELECT count(*) FROM lesson_tries"))
    assert rows == 1
    await _answer_try(h.client, first["try_id"], str(first["dev_answer_latex"]))
    assert (await _try(h.client))["try_id"] != first["try_id"]


async def test_try_it_reveals_the_answer_after_three_misses(api: ApiFactory) -> None:
    h = await _api(api, dev_expose_answers=True)
    problem = await _try(h.client)
    answer = str(problem["dev_answer_latex"])
    results = [
        (await _answer_try(h.client, problem["try_id"], str(int(answer) + n))).json()
        for n in (1, 2, 3)
    ]
    assert [r["attempts_left"] for r in results] == [2, 1, 0]
    assert results[-1]["answer_latex"] == answer
    assert all(r["solved"] is False for r in results)


async def test_try_it_hides_the_answer_by_default_and_is_per_player(api: ApiFactory) -> None:
    h = await _api(api)
    problem = await _try(h.client)
    assert problem["dev_answer_latex"] is None
    other = await api()
    await _signup(other.client, "Other")
    assert (await _answer_try(other.client, problem["try_id"], "1")).status_code == 404
