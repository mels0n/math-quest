"""Admin content preview: the live pack's coverage and every item of a skill, with answers."""

from pathlib import Path
from typing import Any

import pytest

from tests.conftest import Api, ApiFactory

CSRF = {"X-Requested-With": "mathquest"}
PASSWORD = "correct horse battery staple"
LAN = "192.168.1.20"


@pytest.fixture
def password_file(tmp_path: Path) -> Path:
    path = tmp_path / "admin_password"
    path.write_text(PASSWORD + "\n", encoding="utf-8")
    return path


async def _admin(api: ApiFactory, password_file: Path) -> Api:
    h = await api(peer=LAN, admin_password_file=password_file)
    r = await h.client.post("/api/admin/login", json={"password": PASSWORD}, headers=CSRF)
    assert r.status_code == 200
    return h


async def test_content_routes_need_an_admin_session(api: ApiFactory, password_file: Path) -> None:
    h = await api(peer=LAN, admin_password_file=password_file)
    for path in ("/api/admin/content", "/api/admin/content/skills/add_within_20"):
        r = await h.client.get(path)
        assert (r.status_code, r.json()) == (401, {"error": "unauthorized"})


async def test_content_routes_are_hidden_off_lan(api: ApiFactory, password_file: Path) -> None:
    h = await api(peer="203.0.113.9", admin_password_file=password_file)
    assert (await h.client.get("/api/admin/content")).status_code == 404


async def test_overview_shows_the_live_pack_and_coverage(
    api: ApiFactory, password_file: Path
) -> None:
    h = await _admin(api, password_file)
    r = await h.client.get("/api/admin/content")
    assert r.status_code == 200
    (pack,) = r.json()["packs"]
    assert r.json()["targets"]["explanations"] == "3-4"
    assert pack["id"] == "k8-core"
    assert pack["live"] is True
    assert pack["version"] == h.app.state.catalog.pack.version
    meadows = pack["regions"][0]
    assert meadows["region_id"] == "number_meadows"
    skill = next(s for s in meadows["skills"] if s["skill_id"] == "add_within_20")
    assert set(skill) == {
        "skill_id", "name", "tiers", "misconceptions", "feedback", "word_templates", "bank_items",
        "lesson", "hints", "explanations", "gaps",
    }  # fmt: skip
    assert (skill["word_templates"], skill["lesson"], skill["hints"]) == (15, True, 3)
    assert (skill["misconceptions"], skill["feedback"], skill["gaps"]) == (2, 2, [])
    first = next(s for s in meadows["skills"] if s["skill_id"] == "add_within_10")
    assert first["gaps"] == []
    forest = next(r for r in pack["regions"] if r["region_id"] == "fraction_forest")
    fractions = next(s for s in forest["skills"] if s["skill_id"] == "equivalent_fractions")
    assert {"field": "misconception feedback", "have": 0, "want": 3} in fractions["gaps"]


async def test_skill_preview_renders_every_item_with_answers(
    api: ApiFactory, password_file: Path
) -> None:
    h = await _admin(api, password_file)
    r = await h.client.get(
        "/api/admin/content/skills/add_within_20", params={"seed": 42, "tier": 1}
    )
    assert r.status_code == 200
    data: dict[str, Any] = r.json()
    assert (data["skill_id"], data["tier"], data["seeds"]) == ("add_within_20", 1, [42])
    assert data["errors"] == []
    (problem,) = data["problems"]
    expected = h.app.state.catalog.source("add_within_20").generate(42, 1)
    assert problem["answer_latex"] == str(int(expected.answer))
    assert problem["prompt"] == [{"kind": "math", "value": expected.prompt[0].latex}]
    assert [m["key"] for m in problem["misconceptions"]] == ["subtracted_instead", "counted_start"]
    assert all(m["feedback"][0]["kind"] == "text" for m in problem["misconceptions"])
    visual = data["explanations"][0]["visual"]
    assert visual["params"]["start"] == max(expected.values["a"], expected.values["b"])
    assert len(data["lesson"]["screens"]) == 3
    assert data["lesson"]["screens"][1]["visual"]["kind"] == "number_line"
    assert len(data["hints"]) == 3
    a, b = expected.values["a"], expected.values["b"]
    assert {"kind": "math", "value": f"{a} + {b} = {int(expected.answer)}"} in data["hints"][2]
    assert [x["style"] for x in data["explanations"]] == ["visual", "steps", "story", "worked"]
    assert len(data["word_templates"]) == 15
    for template in data["word_templates"]:
        (sample,) = template["samples"]
        assert sample["error"] is None
        assert sample["answer_latex"] == problem["answer_latex"]
        assert all("{" not in part["value"] for part in sample["prompt"])
    assert data["bank_items"] == []
    top = await h.client.get("/api/admin/content/skills/add_within_20", params={"seed": 2**53 - 1})
    assert top.status_code == 200 and top.json()["seeds"] == [2**53 - 1]


async def test_skill_preview_defaults_to_sample_seeds(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    data = (await h.client.get("/api/admin/content/skills/add_within_20")).json()
    assert data["tier"] == 0
    assert data["seeds"] == [1, 2, 3]
    assert len(data["problems"]) == 3
    assert all(len(t["samples"]) == 3 for t in data["word_templates"])


async def test_skill_without_teaching_content(api: ApiFactory, password_file: Path) -> None:
    h = await _admin(api, password_file)
    data = (await h.client.get("/api/admin/content/skills/add_fractions_unlike")).json()
    assert (data["lesson"], data["hints"], data["explanations"]) == (None, None, None)
    assert data["problems"][0]["answer_latex"].startswith("\\frac")


@pytest.mark.parametrize(
    ("path", "params", "status"),
    [
        ("/api/admin/content/skills/no_such_skill", {}, 404),
        ("/api/admin/content/skills/add_within_20", {"tier": 3}, 422),
        ("/api/admin/content/skills/add_within_20", {"tier": -1}, 422),
        ("/api/admin/content/skills/add_within_20", {"seed": -1}, 422),
        ("/api/admin/content/skills/add_within_20", {"seed": 2**53}, 422),
        ("/api/admin/content/skills/Bad-Id", {}, 422),
    ],
)
async def test_skill_preview_rejects_bad_requests(
    api: ApiFactory, password_file: Path, path: str, params: dict[str, int], status: int
) -> None:
    h = await _admin(api, password_file)
    assert (await h.client.get(path, params=params)).status_code == status
