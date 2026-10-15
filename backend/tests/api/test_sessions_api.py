# pyright: reportPrivateUsage=false
"""Practice sessions, the skill list and session summaries over HTTP."""

import httpx
import pytest

from mathquest.engine.scheduler import SESSION_PROBLEMS
from tests.api.test_play_api import CSRF, _answer, _api, _signup
from tests.conftest import ApiFactory


async def _start(client: httpx.AsyncClient, **body: object) -> httpx.Response:
    return await client.post("/api/play/sessions", json=body, headers=CSRF)


async def _next(client: httpx.AsyncClient, session_id: str, version: str) -> httpx.Response:
    return await client.post(
        f"/api/play/sessions/{session_id}/next",
        headers={**CSRF, "X-MathQuest-Client": version},
    )


@pytest.mark.parametrize(
    "body",
    [
        {"mode": "practice"},
        {"mode": "practice", "skill_id": "add_within_10", "weak_spots": True},
        {"mode": "adventure", "skill_id": "add_within_10"},
        {"mode": "adventure", "weak_spots": True},
        {"mode": "practice", "skill_id": "Bad-Id"},
        {"mode": "drill"},
    ],
)
async def test_bad_session_requests_are_422(api: ApiFactory, body: dict[str, object]) -> None:
    h = await _api(api)
    assert (await _start(h.client, **body)).status_code == 422


async def test_practice_start_checks_the_skill(api: ApiFactory) -> None:
    h = await _api(api)
    locked = await _start(h.client, mode="practice", skill_id="add_2digit_regroup")
    assert (locked.status_code, locked.json()) == (409, {"error": "skill_locked"})
    unknown = await _start(h.client, mode="practice", skill_id="no_such_skill")
    assert unknown.status_code == 404
    weak = await _start(h.client, mode="practice", weak_spots=True)
    assert (weak.status_code, weak.json()) == (409, {"error": "no_weak_spots"})

    r = await _start(h.client, mode="practice", skill_id="add_within_10")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "practice"
    assert body["focus"] == [{"skill_id": "add_within_10", "name": "Add to 10"}]
    problem = (await _next(h.client, body["session_id"], "3")).json()
    assert problem["type"] == "problem"
    assert problem["skill_id"] == "add_within_10"
    assert "dev_answer_latex" not in problem or problem["dev_answer_latex"] is None


async def test_the_skill_list(api: ApiFactory) -> None:
    h = await _api(api)
    r = await h.client.get("/api/skills")
    assert r.status_code == 200
    body = r.json()
    assert body["regions"][0] == {"id": "number_meadows", "name": "Number Meadows"}
    first = body["skills"][0]
    assert set(first) == {"skill_id", "name", "region", "state", "progress", "has_lesson"}
    states = {s["skill_id"]: s["state"] for s in body["skills"]}
    assert states["add_within_10"] == "ready"
    assert states["add_2digit_regroup"] == "locked"


async def test_the_skill_list_needs_a_player(api: ApiFactory) -> None:
    h = await api()
    assert (await h.client.get("/api/skills")).status_code == 401


async def test_an_adventure_ends_with_a_summary_only_for_new_clients(api: ApiFactory) -> None:
    h = await _api(api, dev_expose_answers=True)
    new = (await _start(h.client, mode="adventure")).json()["session_id"]
    old = (await _start(h.client, mode="adventure")).json()["session_id"]
    for _ in range(SESSION_PROBLEMS):
        problem = (await _next(h.client, new, "3")).json()
        r = await _answer(h.client, problem["problem_id"], problem["dev_answer_latex"])
        assert r.json()["solved"] is True
        assert (await _next(h.client, old, "2")).json()["type"] == "problem"

    summary = (await _next(h.client, new, "3")).json()
    assert summary["type"] == "summary"
    assert summary["problems_solved"] == SESSION_PROBLEMS
    assert summary["problems_scored"] == SESSION_PROBLEMS
    assert summary["accuracy"] == 1.0
    assert set(summary) == {
        "type",
        "session_id",
        "mode",
        "skills_practiced",
        "newly_mastered",
        "problems_solved",
        "problems_scored",
        "accuracy",
        "seconds",
    }
    ended = await _next(h.client, new, "3")
    assert (ended.status_code, ended.json()) == (409, {"error": "session_ended"})
    # A client from before summaries keeps playing.
    assert (await _next(h.client, old, "2")).json()["type"] == "problem"


async def test_ending_a_session_early(api: ApiFactory) -> None:
    h = await _api(api)
    session_id = (await _start(h.client, mode="adventure")).json()["session_id"]
    problem = (await _next(h.client, session_id, "3")).json()

    r = await h.client.post(f"/api/play/sessions/{session_id}/end", headers=CSRF)
    assert r.status_code == 200
    assert r.json()["type"] == "summary"
    assert r.json()["problems_scored"] == 0
    closed = await _answer(h.client, problem["problem_id"], "1")
    assert (closed.status_code, closed.json()) == (409, {"error": "problem_closed"})

    transport = httpx.ASGITransport(app=h.app, client=("203.0.113.9", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as other:
        await _signup(other, "PlayerTwo")
        r = await other.post(f"/api/play/sessions/{session_id}/end", headers=CSRF)
        assert r.status_code == 404
