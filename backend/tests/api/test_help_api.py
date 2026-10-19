"""Hint, explain and stuck-log routes over HTTP."""

from pathlib import Path
from typing import Any

import httpx
import pytest

from mathquest.engine.checker.bounded import CheckerPool
from mathquest.engine.checker.check import CheckResult, check
from mathquest.engine.types import Problem
from tests.conftest import SIGNUP_WORD, Api, ApiFactory, pass_early_skills

CSRF = {"X-Requested-With": "mathquest"}
PASSWORD = "correct horse battery staple"
LAN = "192.168.1.20"
NICKNAME = "StuckPlayer"


class _SyncPool(CheckerPool):
    async def check(self, problem: Problem, latex: str) -> CheckResult:
        return check(problem, latex)


@pytest.fixture
def password_file(tmp_path: Path) -> Path:
    path = tmp_path / "admin_password"
    path.write_text(PASSWORD + "\n", encoding="utf-8")
    return path


async def _player(api: ApiFactory, password_file: Path) -> Api:
    h = await api(peer=LAN, admin_password_file=password_file, dev_expose_answers=True)
    h.app.state.checker_pool = _SyncPool()
    r = await h.client.post(
        "/api/auth/signup",
        json={"signup_word": SIGNUP_WORD, "nickname": NICKNAME, "pin": "1234"},
        headers=CSRF,
    )
    assert r.status_code == 200
    await pass_early_skills(h)
    for skill_id in h.app.state.catalog.pack.lessons:
        assert (await h.client.post(f"/api/lessons/{skill_id}/seen", headers=CSRF)).is_success
    return h


async def _helpful_problem(client: httpx.AsyncClient) -> dict[str, Any]:
    """The next problem that offers hints and explanations."""
    session = await client.post("/api/play/sessions", json={"mode": "adventure"}, headers=CSRF)
    session_id = session.json()["session_id"]
    for _ in range(12):
        body = (await client.post(f"/api/play/sessions/{session_id}/next", headers=CSRF)).json()
        if body["hint_levels"] == 3 and body["has_explanations"]:
            return body
    raise AssertionError("no problem with hints came up")


async def test_hints_explanations_and_the_stuck_log(api: ApiFactory, password_file: Path) -> None:
    h = await _player(api, password_file)
    problem = await _helpful_problem(h.client)
    base = f"/api/play/problems/{problem['problem_id']}"

    for level in (1, 2, 3):
        r = await h.client.post(f"{base}/hint", headers=CSRF)
        assert r.status_code == 200
        assert (r.json()["level"], r.json()["levels"]) == (level, 3)
    r = await h.client.post(f"{base}/hint", headers=CSRF)
    assert (r.status_code, r.json()) == (409, {"error": "no_more_hints"})

    r = await h.client.post(f"{base}/explain", headers=CSRF)
    assert (r.status_code, r.json()) == (409, {"error": "explain_after_a_try"})
    wrong = str(int(problem["dev_answer_latex"]) + 1000)
    r = await h.client.post(f"{base}/answer", json={"latex": wrong}, headers=CSRF)
    assert r.json()["feedback"] == {
        "kind": "retry",
        "text": [{"kind": "text", "value": r.json()["feedback"]["text"][0]["value"]}],
    }

    count = len(h.app.state.catalog.pack.explanations[problem["skill_id"]].approaches)
    styles: set[str] = set()
    for _ in range(count):
        r = await h.client.post(f"{base}/explain", headers=CSRF)
        assert r.status_code == 200
        assert set(r.json()) == {"approach", "approaches", "style", "body", "visual"}
        styles.add(r.json()["style"])
    assert len(styles) == count

    for k in (1, 2):
        r = await h.client.post(f"{base}/answer", json={"latex": str(int(wrong) + k)}, headers=CSRF)
    assert r.json()["answer_latex"] == problem["dev_answer_latex"]
    r = await h.client.post(f"{base}/hint", headers=CSRF)
    assert (r.status_code, r.json()) == (409, {"error": "problem_scored"})

    assert (await h.client.get("/api/admin/stuck-log")).status_code == 401
    login = await h.client.post("/api/admin/login", json={"password": PASSWORD}, headers=CSRF)
    assert login.status_code == 200

    r = await h.client.get("/api/admin/stuck-log")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "attachment" in r.headers["content-disposition"]
    (entry,) = r.json()
    assert set(entry) == {"skill", "generator", "tier", "seed", "wrong_answers"}
    assert entry["skill"] == problem["skill_id"]
    assert entry["wrong_answers"] == [wrong, str(int(wrong) + 1), str(int(wrong) + 2)]
    assert NICKNAME not in r.text

    r = await h.client.get("/api/admin/stuck-log", params={"format": "csv"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.splitlines()
    assert lines[0] == "skill,generator,tier,seed,wrong_answers"
    assert len(lines) == 2 and NICKNAME not in r.text

    limited = await h.client.get("/api/admin/stuck-log", params={"limit": 1})
    assert len(limited.json()) == 1
    assert (await h.client.get("/api/admin/stuck-log", params={"limit": 0})).status_code == 422
    future = await h.client.get("/api/admin/stuck-log", params={"since": "2999-01-01T00:00:00"})
    assert future.json() == []
    bad = await h.client.get("/api/admin/stuck-log", params={"format": "xml"})
    assert bad.status_code == 422


async def test_help_routes_need_a_player(api: ApiFactory) -> None:
    h = await api()
    for what in ("hint", "explain"):
        r = await h.client.post(
            f"/api/play/problems/00000000-0000-0000-0000-000000000000/{what}", headers=CSRF
        )
        assert r.status_code == 401
