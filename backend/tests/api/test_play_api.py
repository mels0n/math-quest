"""Play routes. Most tests swap in an in-process checker; one uses the real worker pool."""

import uuid

import httpx

from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, check
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


async def _start(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/play/sessions", json={"mode": "adventure"}, headers=CSRF)
    assert r.status_code == 200
    return r.json()["session_id"]


async def _next(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(f"/api/play/sessions/{session_id}/next", headers=CSRF)


async def _answer(client: httpx.AsyncClient, problem_id: str, latex: str) -> httpx.Response:
    return await client.post(
        f"/api/play/problems/{problem_id}/answer", json={"latex": latex}, headers=CSRF
    )


async def _api(api: ApiFactory, *, real_pool: bool = False, **overrides: object) -> Api:
    h = await api(real_pool=real_pool, **overrides)
    if not real_pool:
        h.app.state.checker_pool = _SyncPool()
    await _signup(h.client, "PlayerOne")
    return h


async def test_requires_login(api: ApiFactory) -> None:
    h = await api()
    r = await h.client.post("/api/play/sessions", json={"mode": "adventure"}, headers=CSRF)
    assert r.status_code == 401


async def test_next_problem_hides_answer(api: ApiFactory) -> None:
    h = await _api(api)
    session_id = await _start(h.client)

    r = await _next(h.client, session_id)

    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "problem_id",
        "skill_id",
        "skill_name",
        "prompt_latex",
        "keypad",
        "dev_answer_latex",
    }
    assert body["prompt_latex"]
    assert body["dev_answer_latex"] is None


async def test_dev_answers_off_by_default(api: ApiFactory) -> None:
    h = await _api(api)
    body = (await _next(h.client, await _start(h.client))).json()
    assert body["dev_answer_latex"] is None


async def test_full_round_trip(api: ApiFactory) -> None:
    h = await _api(api, dev_expose_answers=True)
    problem = (await _next(h.client, await _start(h.client))).json()
    assert problem["dev_answer_latex"]

    wrong = await _answer(h.client, problem["problem_id"], "99999")
    assert wrong.status_code == 200
    assert wrong.json()["verdict"] == "incorrect"
    assert wrong.json()["attempts_left"] == 2
    assert wrong.json()["answer_latex"] is None

    right = await _answer(h.client, problem["problem_id"], problem["dev_answer_latex"])
    body = right.json()
    assert body["verdict"] == "correct"
    assert body["solved"] is True
    assert body["answer_latex"] == problem["dev_answer_latex"]
    assert body["mastery"]["skill_id"] == problem["skill_id"]
    assert 0 <= body["mastery"]["progress"] <= 1


async def test_real_checker_pool_end_to_end(api: ApiFactory) -> None:
    h = await _api(api, real_pool=True, dev_expose_answers=True)
    problem = (await _next(h.client, await _start(h.client))).json()

    r = await _answer(h.client, problem["problem_id"], problem["dev_answer_latex"])

    assert r.json()["verdict"] == "correct"


async def test_other_player_gets_404(api: ApiFactory) -> None:
    h = await _api(api)
    session_id = await _start(h.client)
    problem = (await _next(h.client, session_id)).json()

    transport = httpx.ASGITransport(app=h.app, client=("203.0.113.9", 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as other:
        await _signup(other, "PlayerTwo")
        assert (await _next(other, session_id)).status_code == 404
        r = await _answer(other, problem["problem_id"], "1")
        assert r.status_code == 404
        assert r.json() == {"error": "not_found"}


async def test_bad_input_is_422(api: ApiFactory) -> None:
    h = await _api(api)
    bad_mode = await h.client.post("/api/play/sessions", json={"mode": "arcade"}, headers=CSRF)
    assert bad_mode.status_code == 422
    problem = (await _next(h.client, await _start(h.client))).json()
    extra = await h.client.post(
        f"/api/play/problems/{problem['problem_id']}/answer",
        json={"latex": "1", "answer": "2"},
        headers=CSRF,
    )
    assert extra.status_code == 422
    not_uuid = await _answer(h.client, "nope", "1")
    assert not_uuid.status_code == 422


async def test_nul_and_lone_surrogate_answers_are_422(api: ApiFactory) -> None:
    h = await _api(api)
    problem = (await _next(h.client, await _start(h.client))).json()
    url = f"/api/play/problems/{problem['problem_id']}/answer"
    for body in ('{"latex": "1\\u00002"}', '{"latex": "1\\ud8002"}'):
        r = await h.client.post(
            url, content=body, headers={**CSRF, "content-type": "application/json"}
        )
        assert r.status_code == 422, body
        assert r.json() == {"error": "invalid_request"}


async def test_answers_are_rate_limited_per_player(api: ApiFactory) -> None:
    h = await _api(api)
    missing = str(uuid.uuid4())
    for _ in range(60):
        assert (await _answer(h.client, missing, "1")).status_code == 404
    limited = await _answer(h.client, missing, "1")
    assert limited.status_code == 429
    assert limited.json() == {"error": "rate_limited"}
    assert int(limited.headers["Retry-After"]) >= 1
    h.clock.advance(61)
    assert (await _answer(h.client, missing, "1")).status_code == 404


async def test_answering_a_closed_problem_is_409(api: ApiFactory) -> None:
    h = await _api(api)
    session_id = await _start(h.client)
    first = (await _next(h.client, session_id)).json()
    assert (await _next(h.client, session_id)).status_code == 200

    r = await _answer(h.client, first["problem_id"], "1")

    assert r.status_code == 409
    assert r.json() == {"error": "problem_closed"}


async def test_session_creation_is_limited_to_120_per_player_per_minute(api: ApiFactory) -> None:
    h = await _api(api)
    for _ in range(120):
        assert (
            await h.client.post("/api/play/sessions", json={"mode": "adventure"}, headers=CSRF)
        ).status_code == 200
    r = await h.client.post("/api/play/sessions", json={"mode": "adventure"}, headers=CSRF)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    h.clock.advance(61)
    assert (await _start(h.client)) != ""


async def test_next_problem_is_limited_to_120_per_player_per_minute(api: ApiFactory) -> None:
    h = await _api(api)
    session_id = await _start(h.client)
    for _ in range(120):
        assert (await _next(h.client, session_id)).status_code == 200
    r = await _next(h.client, session_id)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
