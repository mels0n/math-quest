import random
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.features.accounts import nicknames, service
from mathquest.shared.config import default_content_dir
from mathquest.shared.errors import Conflict, Invalid, Locked, Unauthorized

WORD = "rainbow"
DEV_A = "device-a"
DEV_B = "device-b"
IP1 = "10.0.0.1"
IP2 = "10.0.0.2"


class Clock:
    def __init__(self) -> None:
        self.t = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += timedelta(seconds=seconds)


@pytest.fixture
async def seeded(db: AsyncSession) -> AsyncSession:
    await service.seed_signup_word(db, WORD)
    return db


@pytest.fixture
def clock() -> Clock:
    return Clock()


async def _signup(
    db: AsyncSession,
    nickname: str = "SwiftOtter42",
    pin: str | None = "1234",
    picture: list[int] | None = None,
) -> service.SignupResult:
    return await service.signup(db, signup_word=WORD, nickname=nickname, pin=pin, picture=picture)


async def _fail_login(
    db: AsyncSession,
    clock: Clock,
    *,
    device: str = DEV_A,
    ip: str = IP1,
    nickname: str = "SwiftOtter42",
) -> None:
    with pytest.raises(Unauthorized):
        await service.login(db, nickname=nickname, pin="0000", device_key=device, ip=ip, now=clock)


async def test_signup_requires_word(seeded: AsyncSession) -> None:
    with pytest.raises(Invalid) as err:
        await service.signup(
            seeded, signup_word="wrong", nickname="SwiftOtter42", pin="1234", picture=None
        )
    assert err.value.code == "signup_word"


async def test_signup_word_is_stored_hashed(seeded: AsyncSession) -> None:
    from mathquest.entities.settings import get_setting

    stored = await get_setting(seeded, "signup_word_hash")
    assert stored is not None
    assert WORD not in stored
    assert stored.startswith("$argon2")


async def test_seed_does_not_overwrite_existing_word(seeded: AsyncSession) -> None:
    await service.seed_signup_word(seeded, "other")
    assert (await _signup(seeded)).player_id is not None


async def test_signup_requires_pin_or_picture(seeded: AsyncSession) -> None:
    with pytest.raises(Invalid) as err:
        await _signup(seeded, pin=None, picture=None)
    assert err.value.code == "credential"


@pytest.mark.parametrize("pin", ["123", "12345", "abcd", "12a4", "١٢٣٤", "1234\n", ""])
async def test_pin_must_be_4_digits(seeded: AsyncSession, pin: str) -> None:
    with pytest.raises(Invalid) as err:
        await _signup(seeded, pin=pin)
    assert err.value.code == "pin"


@pytest.mark.parametrize("picture", [[1, 2, 3], [1, 2, 3, 4, 5], [1, 2, 3, 12], [-1, 0, 1, 2]])
async def test_picture_must_be_4_ids_0_to_11(seeded: AsyncSession, picture: list[int]) -> None:
    with pytest.raises(Invalid) as err:
        await _signup(seeded, pin=None, picture=picture)
    assert err.value.code == "picture"


async def test_signup_with_picture_allows_repeats_and_logs_in(
    seeded: AsyncSession, clock: Clock
) -> None:
    await _signup(seeded, pin=None, picture=[3, 3, 0, 11])
    ok = await service.login(
        seeded, nickname="SwiftOtter42", picture=[3, 3, 0, 11], device_key=DEV_A, ip=IP1, now=clock
    )
    assert ok.device_token
    with pytest.raises(Unauthorized):
        await service.login(
            seeded,
            nickname="SwiftOtter42",
            picture=[3, 3, 0, 10],
            device_key=DEV_A,
            ip=IP1,
            now=clock,
        )


def test_nickname_blocklist_contains() -> None:
    blocklist = frozenset({"butt"})
    assert not nicknames.nickname_allowed("xbutt99", blocklist)
    assert not nicknames.nickname_allowed("Butt_er", blocklist)
    assert nicknames.nickname_allowed("SwiftOtter42", blocklist)


def test_real_blocklist_loads_lowercase_words() -> None:
    words = nicknames.load_blocklist(default_content_dir())
    assert len(words) >= 30
    assert all(w == w.lower() and w.isalpha() for w in words)
    assert "#" not in "".join(words)


async def test_signup_rejects_blocked_nickname(seeded: AsyncSession) -> None:
    with pytest.raises(Invalid) as err:
        await service.signup(
            seeded,
            signup_word=WORD,
            nickname="xbutt99",
            pin="1234",
            picture=None,
            blocklist=frozenset({"butt"}),
        )
    assert err.value.code == "nickname_blocked"


@pytest.mark.parametrize(
    "nickname", ["ab", "a" * 17, "bad!name", "emoji\U0001f600", " lead", "trail "]
)
async def test_signup_rejects_bad_nickname_shape(seeded: AsyncSession, nickname: str) -> None:
    with pytest.raises(Invalid) as err:
        await _signup(seeded, nickname=nickname)
    assert err.value.code == "nickname"


async def test_nickname_unique_case_insensitive(seeded: AsyncSession) -> None:
    await _signup(seeded, nickname="SwiftOtter42")
    with pytest.raises(Conflict) as err:
        await _signup(seeded, nickname="swiftotter42")
    assert err.value.code == "nickname_taken"


def test_suggest_nickname_shape_and_allowed() -> None:
    rng = random.Random(7)
    blocklist = nicknames.load_blocklist(default_content_dir())
    for _ in range(200):
        name = nicknames.suggest_nickname(rng)
        assert nicknames.NICKNAME_RE.fullmatch(name)
        assert nicknames.nickname_allowed(name, blocklist)


def test_content_files_have_expected_sizes() -> None:
    words = nicknames.load_nickname_words(default_content_dir())
    assert len(words.adjectives) == 40
    assert len(words.animals) == 40
    recovery = service.load_recovery_words(default_content_dir())
    assert len(recovery) >= 1000
    assert len(set(recovery)) == len(recovery)
    assert all(re.fullmatch(r"[a-z]{3,9}", w) for w in recovery)
    for path in default_content_dir().glob("*.*"):
        if path.is_file():
            assert "—" not in Path(path).read_text(encoding="utf-8")


async def test_signup_returns_token_and_recovery_word(seeded: AsyncSession) -> None:
    result = await _signup(seeded)
    assert len(result.device_token) >= 43
    assert result.recovery_word.isalpha()
    me = await service.player_for_token(seeded, result.device_token)
    assert me is not None
    assert me.nickname == "SwiftOtter42"
    assert me.id == result.player_id


async def test_only_token_hash_is_stored(seeded: AsyncSession) -> None:
    from sqlalchemy import select

    from mathquest.entities.models import Device

    result = await _signup(seeded)
    rows = (await seeded.execute(select(Device))).scalars().all()
    assert [r.token_hash for r in rows] == [
        __import__("hashlib").sha256(result.device_token.encode()).hexdigest()
    ]


async def test_player_for_unknown_token_is_none(seeded: AsyncSession) -> None:
    assert await service.player_for_token(seeded, "nope") is None


async def test_login_pin_ok_returns_token(seeded: AsyncSession, clock: Clock) -> None:
    signup = await _signup(seeded)
    result = await service.login(
        seeded, nickname="swiftotter42", pin="1234", device_key=DEV_A, ip=IP1, now=clock
    )
    assert result.player_id == signup.player_id
    assert await service.player_for_token(seeded, result.device_token) is not None


async def test_login_unknown_nickname_unauthorized(seeded: AsyncSession, clock: Clock) -> None:
    with pytest.raises(Unauthorized):
        await service.login(
            seeded, nickname="Nobody", pin="1234", device_key=DEV_A, ip=IP1, now=clock
        )


async def test_login_requires_a_credential(seeded: AsyncSession, clock: Clock) -> None:
    await _signup(seeded)
    with pytest.raises(Invalid):
        await service.login(seeded, nickname="SwiftOtter42", device_key=DEV_A, ip=IP1, now=clock)


async def test_lockout_after_5_failures_in_60s(seeded: AsyncSession, clock: Clock) -> None:
    await _signup(seeded)
    for _ in range(5):
        await _fail_login(seeded, clock)
        clock.advance(5)
    with pytest.raises(Locked) as err:
        await service.login(
            seeded, nickname="SwiftOtter42", pin="1234", device_key=DEV_A, ip=IP1, now=clock
        )
    assert 1700 <= err.value.retry_after_s <= 1800


async def test_lockout_expires_after_30_minutes(seeded: AsyncSession, clock: Clock) -> None:
    await _signup(seeded)
    for _ in range(5):
        await _fail_login(seeded, clock)
    clock.advance(30 * 60 + 1)
    ok = await service.login(
        seeded, nickname="SwiftOtter42", pin="1234", device_key=DEV_A, ip=IP1, now=clock
    )
    assert ok.device_token


async def test_lockout_scoped_to_device_and_ip(seeded: AsyncSession, clock: Clock) -> None:
    signup = await _signup(seeded)
    other_token = (
        await service.login(
            seeded, nickname="SwiftOtter42", pin="1234", device_key=DEV_B, ip=IP1, now=clock
        )
    ).device_token
    for _ in range(5):
        await _fail_login(seeded, clock, device=DEV_A, ip=IP1)
    with pytest.raises(Locked):
        await service.login(
            seeded, nickname="SwiftOtter42", pin="1234", device_key=DEV_A, ip=IP1, now=clock
        )
    for device, ip in ((DEV_B, IP1), (DEV_A, IP2)):
        ok = await service.login(
            seeded, nickname="SwiftOtter42", pin="1234", device_key=device, ip=ip, now=clock
        )
        assert ok.player_id == signup.player_id
    me = await service.player_for_token(seeded, other_token, now=clock)
    assert me is not None
    assert me.id == signup.player_id


async def test_lockout_does_not_cross_players(seeded: AsyncSession, clock: Clock) -> None:
    await _signup(seeded, nickname="SwiftOtter42")
    await _signup(seeded, nickname="BraveLynx11", pin="4321")
    for _ in range(5):
        await _fail_login(seeded, clock)
    ok = await service.login(
        seeded, nickname="BraveLynx11", pin="4321", device_key=DEV_A, ip=IP1, now=clock
    )
    assert ok.device_token


async def test_failures_older_than_60s_do_not_count(seeded: AsyncSession, clock: Clock) -> None:
    await _signup(seeded)
    for _ in range(4):
        await _fail_login(seeded, clock)
    clock.advance(61)
    await _fail_login(seeded, clock)
    ok = await service.login(
        seeded, nickname="SwiftOtter42", pin="1234", device_key=DEV_A, ip=IP1, now=clock
    )
    assert ok.device_token


async def test_recover_resets_pin(seeded: AsyncSession, clock: Clock) -> None:
    signup = await _signup(seeded)
    result = await service.recover(
        seeded,
        nickname="SwiftOtter42",
        recovery_word=signup.recovery_word.upper(),
        new_pin="9876",
        device_key=DEV_A,
        ip=IP1,
        now=clock,
    )
    assert result.player_id == signup.player_id
    assert await service.player_for_token(seeded, result.device_token) is not None
    with pytest.raises(Unauthorized):
        await service.login(
            seeded, nickname="SwiftOtter42", pin="1234", device_key=DEV_A, ip=IP1, now=clock
        )
    ok = await service.login(
        seeded, nickname="SwiftOtter42", pin="9876", device_key=DEV_A, ip=IP1, now=clock
    )
    assert ok.player_id == signup.player_id


async def test_recover_with_new_picture(seeded: AsyncSession, clock: Clock) -> None:
    signup = await _signup(seeded)
    await service.recover(
        seeded,
        nickname="SwiftOtter42",
        recovery_word=signup.recovery_word,
        new_picture=[0, 1, 2, 3],
        device_key=DEV_A,
        ip=IP1,
        now=clock,
    )
    ok = await service.login(
        seeded, nickname="SwiftOtter42", picture=[0, 1, 2, 3], device_key=DEV_A, ip=IP1, now=clock
    )
    assert ok.player_id == signup.player_id


async def test_recover_wrong_word_unauthorized(seeded: AsyncSession, clock: Clock) -> None:
    await _signup(seeded)
    with pytest.raises(Unauthorized):
        await service.recover(
            seeded,
            nickname="SwiftOtter42",
            recovery_word="zzzzzz",
            new_pin="9876",
            device_key=DEV_A,
            ip=IP1,
            now=clock,
        )


async def test_recovery_guesses_share_lockout(seeded: AsyncSession, clock: Clock) -> None:
    signup = await _signup(seeded)
    for _ in range(3):
        await _fail_login(seeded, clock)
    for _ in range(2):
        with pytest.raises(Unauthorized):
            await service.recover(
                seeded,
                nickname="SwiftOtter42",
                recovery_word="zzzzzz",
                new_pin="9876",
                device_key=DEV_A,
                ip=IP1,
                now=clock,
            )
    with pytest.raises(Locked):
        await service.recover(
            seeded,
            nickname="SwiftOtter42",
            recovery_word=signup.recovery_word,
            new_pin="9876",
            device_key=DEV_A,
            ip=IP1,
            now=clock,
        )
    with pytest.raises(Locked):
        await service.login(
            seeded, nickname="SwiftOtter42", pin="1234", device_key=DEV_A, ip=IP1, now=clock
        )


async def test_no_pii_columns(db: AsyncSession) -> None:
    def columns(sync_conn: object) -> set[str]:
        from sqlalchemy.engine import Connection

        assert isinstance(sync_conn, Connection)
        return {c["name"] for c in inspect(sync_conn).get_columns("players")}

    conn = await db.connection()
    names = await conn.run_sync(columns)
    assert {"id", "nickname", "nickname_key"} <= names
    for name in names:
        for banned in ("email", "name", "age", "birth"):
            assert banned not in name.replace("nickname", ""), name


async def test_rotating_device_keys_from_one_ip_locks_the_pair(
    seeded: AsyncSession, clock: Clock
) -> None:
    signup = await _signup(seeded)
    for i in range(15):
        await _fail_login(seeded, clock, device=f"rot-{i}", ip=IP1)
        clock.advance(1)
    with pytest.raises(Locked) as err:
        await service.login(
            seeded, nickname="SwiftOtter42", pin="1234", device_key="fresh", ip=IP1, now=clock
        )
    assert 1700 <= err.value.retry_after_s <= 1800
    ok = await service.login(
        seeded, nickname="SwiftOtter42", pin="1234", device_key="fresh", ip=IP2, now=clock
    )
    assert ok.player_id == signup.player_id
    me = await service.player_for_token(seeded, signup.device_token, now=clock)
    assert me is not None


async def test_fourteen_rotated_failures_do_not_lock(seeded: AsyncSession, clock: Clock) -> None:
    await _signup(seeded)
    for i in range(14):
        await _fail_login(seeded, clock, device=f"rot-{i}", ip=IP1)
    ok = await service.login(
        seeded, nickname="SwiftOtter42", pin="1234", device_key="fresh", ip=IP1, now=clock
    )
    assert ok.device_token


async def test_reserved_device_key_rejected(seeded: AsyncSession, clock: Clock) -> None:
    await _signup(seeded)
    with pytest.raises(Invalid):
        await service.login(
            seeded, nickname="SwiftOtter42", pin="1234", device_key="*", ip=IP1, now=clock
        )


async def test_recover_rotates_word_and_revokes_old_devices(
    seeded: AsyncSession, clock: Clock
) -> None:
    signup = await _signup(seeded)
    result = await service.recover(
        seeded,
        nickname="SwiftOtter42",
        recovery_word=signup.recovery_word,
        new_pin="9876",
        device_key=DEV_A,
        ip=IP1,
        now=clock,
    )
    assert result.recovery_word != signup.recovery_word
    assert await service.player_for_token(seeded, signup.device_token) is None
    assert await service.player_for_token(seeded, result.device_token) is not None
    with pytest.raises(Unauthorized):
        await service.recover(
            seeded,
            nickname="SwiftOtter42",
            recovery_word=signup.recovery_word,
            new_pin="1111",
            device_key=DEV_A,
            ip=IP1,
            now=clock,
        )
    again = await service.recover(
        seeded,
        nickname="SwiftOtter42",
        recovery_word=result.recovery_word,
        new_pin="2222",
        device_key=DEV_A,
        ip=IP1,
        now=clock,
    )
    assert again.player_id == signup.player_id


async def test_unknown_nickname_still_spends_a_verify(
    seeded: AsyncSession, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str | None] = []
    real = service._verify  # pyright: ignore[reportPrivateUsage]

    async def spy(stored: str | None, secret: str) -> bool:
        calls.append(stored)
        return await real(stored, secret)

    monkeypatch.setattr(service, "_verify", spy)
    with pytest.raises(Unauthorized):
        await service.login(
            seeded, nickname="Nobody", pin="1234", device_key=DEV_A, ip=IP1, now=clock
        )
    assert calls == [None]


def test_hasher_uses_pinned_argon2_parameters() -> None:
    hasher = service._hasher  # pyright: ignore[reportPrivateUsage]
    assert (hasher.memory_cost, hasher.time_cost, hasher.parallelism) == (19456, 2, 1)


async def test_old_failures_are_pruned(seeded: AsyncSession, clock: Clock) -> None:
    from sqlalchemy import func, select

    from mathquest.entities.models import AuthFailure

    await _signup(seeded)
    await _fail_login(seeded, clock)
    clock.advance(3601)
    await _fail_login(seeded, clock)
    count = (await seeded.execute(select(func.count()).select_from(AuthFailure))).scalar_one()
    assert count == 1


async def test_hidden_player_cannot_log_in(seeded: AsyncSession, clock: Clock) -> None:
    from sqlalchemy import update

    from mathquest.entities.models import Player

    await _signup(seeded)
    await seeded.execute(update(Player).values(hidden=True))
    with pytest.raises(Unauthorized):
        await service.login(
            seeded, nickname="SwiftOtter42", pin="1234", device_key=DEV_A, ip=IP1, now=clock
        )


async def test_seed_accepts_secret_str(db: AsyncSession) -> None:
    from pydantic import SecretStr

    await service.seed_signup_word(db, SecretStr("sesame"))
    result = await service.signup(
        db, signup_word="sesame", nickname="SwiftOtter42", pin="1234", picture=None
    )
    assert result.player_id is not None


async def _fail_recover(
    db: AsyncSession, clock: Clock, *, device: str, ip: str = IP1, word: str = "zzzzzz"
) -> None:
    with pytest.raises(Unauthorized):
        await service.recover(
            db,
            nickname="SwiftOtter42",
            recovery_word=word,
            new_pin="9876",
            device_key=device,
            ip=ip,
            now=clock,
        )


async def test_ten_failed_recoveries_across_addresses_disable_recovery_for_a_day(
    seeded: AsyncSession, clock: Clock
) -> None:
    signup = await _signup(seeded)
    for i in range(10):
        await _fail_recover(seeded, clock, device=f"dev-{i}", ip=f"10.0.1.{i}")
        clock.advance(60)
    with pytest.raises(Locked) as err:
        await service.recover(
            seeded,
            nickname="SwiftOtter42",
            recovery_word=signup.recovery_word,
            new_pin="9876",
            device_key="brand-new",
            ip="10.0.9.9",
            now=clock,
        )
    assert 86_300 <= err.value.retry_after_s <= 86_400
    login = await service.login(
        seeded,
        nickname="SwiftOtter42",
        pin="1234",
        device_key="brand-new",
        ip="10.0.9.9",
        now=clock,
    )
    assert login.player_id == signup.player_id
    clock.advance(86_400)
    result = await service.recover(
        seeded,
        nickname="SwiftOtter42",
        recovery_word=signup.recovery_word,
        new_pin="9876",
        device_key="brand-new",
        ip="10.0.9.9",
        now=clock,
    )
    assert result.player_id == signup.player_id


async def test_nine_failed_recoveries_do_not_disable_recovery(
    seeded: AsyncSession, clock: Clock
) -> None:
    signup = await _signup(seeded)
    for i in range(9):
        await _fail_recover(seeded, clock, device=f"dev-{i}", ip=f"10.0.1.{i}")
    result = await service.recover(
        seeded,
        nickname="SwiftOtter42",
        recovery_word=signup.recovery_word,
        new_pin="9876",
        device_key="brand-new",
        ip="10.0.9.9",
        now=clock,
    )
    assert result.player_id == signup.player_id


async def test_failed_recoveries_older_than_a_day_do_not_count(
    seeded: AsyncSession, clock: Clock
) -> None:
    signup = await _signup(seeded)
    for i in range(9):
        await _fail_recover(seeded, clock, device=f"dev-{i}", ip=f"10.0.1.{i}")
    clock.advance(86_401)
    await _fail_recover(seeded, clock, device="late", ip="10.0.2.1")
    result = await service.recover(
        seeded,
        nickname="SwiftOtter42",
        recovery_word=signup.recovery_word,
        new_pin="9876",
        device_key="brand-new",
        ip="10.0.9.9",
        now=clock,
    )
    assert result.player_id == signup.player_id
