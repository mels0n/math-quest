import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities import credentials, lockouts, mastery, players
from mathquest.entities.admin import AdminAudit
from mathquest.entities.models import AppSetting, AuthFailure, Device, Lockout, Player
from mathquest.entities.problems import add_attempt, add_problem, add_session
from mathquest.features import admin
from mathquest.features.accounts import service as accounts
from mathquest.shared.config import default_content_dir
from mathquest.shared.errors import Conflict, Invalid, Locked, NotFound, Unauthorized

WORD = "rainbow"
SESSION = uuid.uuid4()
NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
async def seeded(db: AsyncSession) -> AsyncSession:
    await accounts.seed_signup_word(db, WORD)
    return db


async def _signup(db: AsyncSession, nickname: str, pin: str = "1234") -> accounts.SignupResult:
    return await accounts.signup(db, signup_word=WORD, nickname=nickname, pin=pin, picture=None)


async def _signup_ordered(db: AsyncSession, *names: str) -> list[accounts.SignupResult]:
    """Sign up in order with strictly increasing created_at (now() is fixed inside one test)."""
    results: list[accounts.SignupResult] = []
    for i, name in enumerate(names):
        r = await _signup(db, name)
        await db.execute(
            text("UPDATE players SET created_at = :t WHERE id = :p"),
            {"t": datetime(2026, 1, 1, 0, i, tzinfo=UTC), "p": r.player_id},
        )
        results.append(r)
    return results


async def _login(db: AsyncSession, nickname: str, pin: str = "1234") -> accounts.LoginResult:
    return await accounts.login(db, nickname=nickname, pin=pin, device_key="dev", ip="10.0.0.1")


async def _audit_rows(db: AsyncSession) -> list[AdminAudit]:
    result = await db.execute(select(AdminAudit).order_by(AdminAudit.id))
    return list(result.scalars().all())


async def test_list_is_newest_first_with_hidden_flag_and_last_seen(seeded: AsyncSession) -> None:
    a, _ = await _signup_ordered(seeded, "Alpha", "Bravo")
    await admin.set_hidden(seeded, SESSION, a.player_id, True)
    rows = await admin.list_players(seeded)
    assert [r.nickname for r in rows] == ["Bravo", "Alpha"]
    assert [r.hidden for r in rows] == [False, True]
    assert all(r.last_seen is not None for r in rows)
    assert set(admin.PlayerAdminOut.model_fields) == {
        "id",
        "nickname",
        "hidden",
        "created_at",
        "last_seen",
    }


async def test_search_matches_anywhere_case_insensitively(seeded: AsyncSession) -> None:
    for name in ("SwiftOtter", "otterFan", "Zebra"):
        await _signup(seeded, name)
    found = await admin.list_players(seeded, query="OTTER")
    assert sorted(r.nickname for r in found) == ["SwiftOtter", "otterFan"]


async def test_search_treats_like_wildcards_literally(seeded: AsyncSession) -> None:
    await _signup_ordered(seeded, "Under_score", "UnderXscore")
    assert [r.nickname for r in await admin.list_players(seeded, query="r_s")] == ["Under_score"]
    assert await admin.list_players(seeded, query="%") == []
    assert await admin.list_players(seeded, query="r%s") == []


async def test_paging_clamps_limit_and_offsets(seeded: AsyncSession) -> None:
    await _signup_ordered(seeded, *(f"Player{i}" for i in range(5)))
    assert len(await admin.list_players(seeded, limit=2)) == 2
    assert [r.nickname for r in await admin.list_players(seeded, offset=3, limit=50)] == [
        "Player1",
        "Player0",
    ]
    assert len(await admin.list_players(seeded, limit=10_000)) == 5


async def test_hidden_player_is_unknown_to_login_and_recover(seeded: AsyncSession) -> None:
    s = await _signup(seeded, "Alpha")
    await admin.set_hidden(seeded, SESSION, s.player_id, True)
    with pytest.raises(Unauthorized):
        await _login(seeded, "Alpha")
    with pytest.raises(Unauthorized):
        await accounts.recover(
            seeded,
            nickname="Alpha",
            recovery_word=s.recovery_word,
            new_pin="4321",
            device_key="dev",
            ip="10.0.0.1",
        )
    await admin.set_hidden(seeded, SESSION, s.player_id, False)
    await _login(seeded, "Alpha")


async def test_rename_applies_signup_rules(seeded: AsyncSession) -> None:
    a = await _signup(seeded, "Alpha")
    await _signup(seeded, "Bravo")
    await admin.rename(seeded, SESSION, a.player_id, "Charlie")
    await _login(seeded, "Charlie")
    with pytest.raises(Unauthorized):
        await _login(seeded, "Alpha")
    with pytest.raises(Conflict):
        await admin.rename(seeded, SESSION, a.player_id, "BRAVO")
    with pytest.raises(Invalid):
        await admin.rename(seeded, SESSION, a.player_id, "x")
    with pytest.raises(Invalid):
        await admin.rename(seeded, SESSION, a.player_id, "bad!name")
    with pytest.raises(Invalid):
        await admin.rename(seeded, SESSION, a.player_id, "Fu Ck", blocklist=frozenset({"fuck"}))
    await admin.rename(seeded, SESSION, a.player_id, "CHARLIE")
    assert "CHARLIE" in [r.nickname for r in await admin.list_players(seeded)]


async def test_unknown_player_is_not_found_and_not_audited(seeded: AsyncSession) -> None:
    ghost = uuid.uuid4()
    with pytest.raises(NotFound):
        await admin.set_hidden(seeded, SESSION, ghost, True)
    with pytest.raises(NotFound):
        await admin.rename(seeded, SESSION, ghost, "Whoever")
    with pytest.raises(NotFound):
        await admin.reset_pin(seeded, SESSION, ghost, "1234")
    with pytest.raises(NotFound):
        await admin.delete_player(seeded, SESSION, ghost)
    assert await _audit_rows(seeded) == []


async def test_reset_pin_rotates_word_and_revokes_devices(seeded: AsyncSession) -> None:
    s = await _signup(seeded, "Alpha")
    out = await admin.reset_pin(seeded, SESSION, s.player_id, "9876")
    assert out.recovery_word != s.recovery_word
    assert out.recovery_word in accounts.load_recovery_words(default_content_dir())
    assert await accounts.player_for_token(seeded, s.device_token) is None
    live = await seeded.execute(
        select(func.count()).select_from(Device).where(Device.revoked.is_(False))
    )
    assert live.scalar_one() == 0
    with pytest.raises(Unauthorized):
        await _login(seeded, "Alpha", "1234")
    await _login(seeded, "Alpha", "9876")
    with pytest.raises(Unauthorized):
        await accounts.recover(
            seeded,
            nickname="Alpha",
            recovery_word=s.recovery_word,
            new_pin="1111",
            device_key="dev",
            ip="10.0.0.1",
        )
    recovered = await accounts.recover(
        seeded,
        nickname="Alpha",
        recovery_word=out.recovery_word,
        new_pin="1111",
        device_key="dev2",
        ip="10.0.0.2",
    )
    assert recovered.recovery_word != out.recovery_word


async def test_reset_pin_never_reissues_the_current_word(seeded: AsyncSession) -> None:
    s = await _signup(seeded, "Alpha")
    word = s.recovery_word
    for _ in range(8):
        out = await admin.reset_pin(seeded, SESSION, s.player_id, "1234")
        assert out.recovery_word != word
        word = out.recovery_word


async def test_reset_pin_rejects_a_bad_pin(seeded: AsyncSession) -> None:
    s = await _signup(seeded, "Alpha")
    with pytest.raises(Invalid):
        await admin.reset_pin(seeded, SESSION, s.player_id, "12a4")
    await _login(seeded, "Alpha")


TABLES = (
    "devices",
    "auth_failures",
    "lockouts",
    "recovery_failures",
    "play_sessions",
    "problem_instances",
    "attempts",
    "skill_mastery",
)


async def _populate(db: AsyncSession, player_id: uuid.UUID) -> None:
    sess = await add_session(db, player_id=player_id, mode="practice", started_at=NOW)
    problem = await add_problem(
        db,
        session_id=sess.id,
        player_id=player_id,
        skill_id="s",
        tier=1,
        seed=1,
        difficulty=0.5,
        issued_at=NOW,
    )
    await add_attempt(
        db,
        problem_id=problem.id,
        player_id=player_id,
        latex="1",
        verdict="correct",
        misconception=None,
        seconds=1.0,
        at=NOW,
    )
    await mastery.lock(db, player_id, "s", 1000.0)
    params = {"p": player_id, "t": NOW}
    await db.execute(
        text(
            "INSERT INTO auth_failures (player_id, device_key, ip, at) "
            "VALUES (:p, 'k', '10.0.0.9', :t)"
        ),
        params,
    )
    await db.execute(
        text(
            "INSERT INTO lockouts (player_id, device_key, ip, until) "
            "VALUES (:p, 'k', '10.0.0.9', :t)"
        ),
        params,
    )
    await db.execute(text("INSERT INTO recovery_failures (player_id, at) VALUES (:p, :t)"), params)
    await db.flush()


async def _counts(db: AsyncSession, player_id: uuid.UUID) -> dict[str, int]:
    out: dict[str, int] = {}
    for table in TABLES:
        result = await db.execute(
            text(f"SELECT count(*) FROM {table} WHERE player_id = :p"), {"p": player_id}
        )
        out[table] = result.scalar_one()
    return out


async def test_delete_removes_every_row_of_that_player_only(seeded: AsyncSession) -> None:
    a = await _signup(seeded, "Alpha")
    b = await _signup(seeded, "Bravo")
    await _populate(seeded, a.player_id)
    await _populate(seeded, b.player_id)
    before = await _counts(seeded, b.player_id)
    assert all(n >= 1 for n in before.values())
    assert all(n >= 1 for n in (await _counts(seeded, a.player_id)).values())

    await admin.delete_player(seeded, SESSION, a.player_id)

    assert all(n == 0 for n in (await _counts(seeded, a.player_id)).values())
    assert await _counts(seeded, b.player_id) == before
    assert [r.nickname for r in await admin.list_players(seeded)] == ["Bravo"]
    await _login(seeded, "Bravo")


async def test_every_action_writes_one_audit_row(seeded: AsyncSession) -> None:
    s = await _signup(seeded, "Alpha")
    await admin.set_hidden(seeded, SESSION, s.player_id, True)
    await admin.set_hidden(seeded, SESSION, s.player_id, False)
    await admin.rename(seeded, SESSION, s.player_id, "Beta")
    await admin.reset_pin(seeded, SESSION, s.player_id, "1234")
    await admin.set_signup_word(seeded, SESSION, "newword")
    await admin.delete_player(seeded, SESSION, s.player_id)
    rows = await _audit_rows(seeded)
    assert [r.action for r in rows] == [
        "hide",
        "unhide",
        "rename",
        "reset_pin",
        "signup_word",
        "delete",
    ]
    assert all(r.admin_session_id == SESSION for r in rows)
    assert [r.target_nickname for r in rows] == ["Alpha", "Alpha", "Alpha", "Beta", None, "Beta"]
    assert [r.detail for r in rows] == [None, None, "Beta", None, None, None]


async def test_deleted_player_stays_attributable(seeded: AsyncSession) -> None:
    s = await _signup(seeded, "Alpha")
    await admin.delete_player(seeded, SESSION, s.player_id)
    (row,) = await _audit_rows(seeded)
    assert row.player_id is None
    assert row.target_nickname == "Alpha"


async def test_signup_word_change_applies_to_next_signup(seeded: AsyncSession) -> None:
    assert await admin.signup_word_is_set(seeded)
    await admin.set_signup_word(seeded, SESSION, "Sunshine")
    with pytest.raises(Invalid):
        await _signup(seeded, "Alpha")
    ok = await accounts.signup(
        seeded, signup_word="Sunshine", nickname="Alpha", pin="1234", picture=None
    )
    assert ok.player_id
    stored = (await seeded.execute(select(AppSetting.value))).scalars().all()
    assert all("Sunshine" not in v for v in stored)
    assert any(v.startswith("$argon2") for v in stored)


@pytest.mark.parametrize("word", ["ab", "a" * 33, "has space", "dig1ts", "naïve", "", "x-y"])
async def test_signup_word_must_be_three_to_32_ascii_letters(
    seeded: AsyncSession, word: str
) -> None:
    with pytest.raises(Invalid):
        await admin.set_signup_word(seeded, SESSION, word)
    assert await _audit_rows(seeded) == []
    await _signup(seeded, "Alpha")


async def test_signup_word_is_set_reflects_state(db: AsyncSession) -> None:
    assert not await admin.signup_word_is_set(db)
    await admin.set_signup_word(db, SESSION, "abc")
    assert await admin.signup_word_is_set(db)


class _Clock:
    def __init__(self) -> None:
        self.t = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.t


async def test_reset_pin_lifts_lockouts_and_failures(seeded: AsyncSession) -> None:
    s = await _signup(seeded, "Alpha")
    clock = _Clock()
    for _ in range(5):
        with pytest.raises(Unauthorized):
            await accounts.login(
                seeded, nickname="Alpha", pin="0000", device_key="dev", ip="10.0.0.1", now=clock
            )
    with pytest.raises(Locked):
        await accounts.login(
            seeded, nickname="Alpha", pin="1234", device_key="dev", ip="10.0.0.1", now=clock
        )
    await seeded.execute(
        text("UPDATE players SET recovery_locked_until = :t WHERE id = :p"),
        {"t": clock.t + timedelta(hours=5), "p": s.player_id},
    )
    await seeded.execute(
        text("INSERT INTO recovery_failures (player_id, at) VALUES (:p, :t)"),
        {"p": s.player_id, "t": clock.t},
    )

    await admin.reset_pin(seeded, SESSION, s.player_id, "5555")

    await accounts.login(
        seeded, nickname="Alpha", pin="5555", device_key="dev", ip="10.0.0.1", now=clock
    )
    for model in (Lockout, AuthFailure):
        count = await seeded.execute(select(func.count()).select_from(model))
        assert count.scalar_one() == 0
    row = await seeded.execute(
        text(
            "SELECT recovery_locked_until, (SELECT count(*) FROM recovery_failures) "
            "FROM players WHERE id = :p"
        ),
        {"p": s.player_id},
    )
    assert tuple(row.one()) == (None, 0)


def _db_error(sqlstate: str) -> DBAPIError:
    class Orig(Exception):
        pass

    orig = Orig()
    orig.sqlstate = sqlstate  # pyright: ignore[reportAttributeAccessIssue]
    return DBAPIError("DELETE", {}, orig)


async def test_delete_retries_once_after_a_deadlock(
    seeded: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = await _signup(seeded, "Alpha")
    real = players.delete_player
    calls = 0

    async def flaky(db: AsyncSession, player_id: uuid.UUID) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _db_error("40P01")
        await real(db, player_id)

    monkeypatch.setattr(players, "delete_player", flaky)
    await admin.delete_player(seeded, SESSION, s.player_id)
    assert calls == 2
    assert await admin.list_players(seeded) == []
    assert [r.action for r in await _audit_rows(seeded)] == ["delete"]


async def test_delete_that_deadlocks_twice_is_busy_and_changes_nothing(
    seeded: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = await _signup(seeded, "Alpha")

    async def always(db: AsyncSession, player_id: uuid.UUID) -> None:
        raise _db_error("40P01")

    monkeypatch.setattr(players, "delete_player", always)
    with pytest.raises(Conflict) as info:
        await admin.delete_player(seeded, SESSION, s.player_id)
    assert info.value.code == "busy"
    assert [r.nickname for r in await admin.list_players(seeded)] == ["Alpha"]
    assert await _audit_rows(seeded) == []


async def test_delete_does_not_swallow_other_database_errors(
    seeded: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = await _signup(seeded, "Alpha")

    async def broken(db: AsyncSession, player_id: uuid.UUID) -> None:
        raise _db_error("23503")

    monkeypatch.setattr(players, "delete_player", broken)
    with pytest.raises(DBAPIError):
        await admin.delete_player(seeded, SESSION, s.player_id)


async def test_rename_losing_the_unique_race_is_a_conflict(
    seeded: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = await _signup(seeded, "Alpha")
    await _signup(seeded, "Bravo")

    async def no_check(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(credentials, "check_nickname_available", no_check)
    with pytest.raises(Conflict) as info:
        await admin.rename(seeded, SESSION, a.player_id, "bravo")
    assert info.value.code == "nickname_taken"
    assert sorted(r.nickname for r in await admin.list_players(seeded)) == ["Alpha", "Bravo"]
    assert await _audit_rows(seeded) == []


def _delete_before_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    real = lockouts.lock_player

    async def delete_then_lock(db: AsyncSession, player_id: uuid.UUID) -> bool:
        await db.execute(delete(Player).where(Player.id == player_id))
        return await real(db, player_id)

    monkeypatch.setattr(lockouts, "lock_player", delete_then_lock)


@pytest.mark.parametrize("flow", ["login", "recover"])
async def test_attempt_racing_a_delete_is_unauthorized_not_a_crash(
    seeded: AsyncSession, monkeypatch: pytest.MonkeyPatch, flow: str
) -> None:
    s = await _signup(seeded, "Alpha")
    _delete_before_lock(monkeypatch)
    with pytest.raises(Unauthorized):
        if flow == "login":
            await _login(seeded, "Alpha")
        else:
            await accounts.recover(
                seeded,
                nickname="Alpha",
                recovery_word=s.recovery_word,
                new_pin="4321",
                device_key="dev",
                ip="10.0.0.1",
            )


async def test_reset_pin_on_a_player_deleted_before_the_lock_is_not_found(
    seeded: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = await _signup(seeded, "Alpha")
    _delete_before_lock(monkeypatch)
    with pytest.raises(NotFound):
        await admin.reset_pin(seeded, SESSION, s.player_id, "4321")
