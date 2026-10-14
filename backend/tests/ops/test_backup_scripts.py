"""Drives deploy/backup scripts against throwaway databases on the test server.

Skipped when the PostgreSQL client tools are not on PATH. Each test creates
uniquely named databases and drops them afterwards.
"""

import asyncio
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKUP = REPO_ROOT / "deploy" / "backup" / "pg-backup.sh"
RESTORE = REPO_ROOT / "deploy" / "backup" / "pg-restore.sh"
TOOLS = ("pg_dump", "pg_restore", "psql", "sh")

pytestmark = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in TOOLS),
    reason="PostgreSQL client tools (pg_dump, pg_restore, psql) are not on PATH",
)


def _server_url() -> URL:
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.fail("TEST_DATABASE_URL is not set (asyncpg URL of a throwaway Postgres)")
    return make_url(raw)


async def _run_sql(database: str | None, statements: list[str]) -> list[dict[str, Any]]:
    url = _server_url().set(database=database or _server_url().database)
    engine = create_async_engine(url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        rows: list[dict[str, Any]] = []
        async with engine.connect() as conn:
            for statement in statements:
                result = await conn.execute(text(statement))
                rows = [dict(row) for row in result.mappings()] if result.returns_rows else []
        return rows
    finally:
        await engine.dispose()


def _new_database() -> str:
    name = f"mq_bk_{uuid.uuid4().hex[:12]}"
    asyncio.run(_run_sql(None, [f'CREATE DATABASE "{name}"']))
    return name


def _drop_database(name: str) -> None:
    asyncio.run(_run_sql(None, [f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)']))


@pytest.fixture
def source_db() -> Iterator[str]:
    name = _new_database()
    try:
        asyncio.run(
            _run_sql(
                name,
                [
                    "CREATE TABLE players (id serial PRIMARY KEY, nickname text NOT NULL)",
                    "CREATE TABLE attempts (id serial PRIMARY KEY,"
                    " player_id int NOT NULL REFERENCES players(id), correct boolean NOT NULL)",
                    "INSERT INTO players (nickname) SELECT 'p' || g FROM generate_series(1, 3) g",
                    "INSERT INTO attempts (player_id, correct)"
                    " SELECT 1 + g % 3, g % 2 = 0 FROM generate_series(1, 7) g",
                ],
            )
        )
        yield name
    finally:
        _drop_database(name)


@pytest.fixture
def target_db() -> Iterator[str]:
    name = _new_database()
    try:
        yield name
    finally:
        _drop_database(name)


def _write_password(directory: Path, password: str | None = None) -> Path:
    path = directory / "db_password"
    path.write_text((_server_url().password or "") if password is None else password)
    path.chmod(0o600)
    return path


def _env(database: str, password_file: Path, backup_dir: Path, **extra: str) -> dict[str, str]:
    url = _server_url()
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", "/tmp"),
        "PGHOST": url.host or "localhost",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "",
        "PGDATABASE": database,
        "PGPASSWORD_FILE": str(password_file),
        "BACKUP_DIR": str(backup_dir),
    }
    env.update(extra)
    return env


def _run(script: Path, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(script), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _counts(database: str) -> dict[str, int]:
    rows = asyncio.run(
        _run_sql(
            database,
            [
                "SELECT 'public.players' AS t, count(*) AS c FROM players"
                " UNION ALL SELECT 'public.attempts', count(*) FROM attempts"
            ],
        )
    )
    return {row["t"]: row["c"] for row in rows}


def _parse_counts(stdout: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            out[parts[0]] = int(parts[1])
    return out


def _dumps(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.dump"))


def test_once_creates_one_dump_and_no_partial(source_db: str, tmp_path: Path) -> None:
    pw = _write_password(tmp_path)
    out = tmp_path / "backups"
    out.mkdir()
    result = _run(BACKUP, ["--once"], _env(source_db, pw, out))
    assert result.returncode == 0, result.stderr
    assert len(_dumps(out)) == 1
    assert _dumps(out)[0].stat().st_size > 0
    assert list(out.glob("*.partial")) == []


def test_prune_keeps_newest_and_ignores_other_files(source_db: str, tmp_path: Path) -> None:
    pw = _write_password(tmp_path)
    out = tmp_path / "backups"
    out.mkdir()
    for day in range(1, 6):
        (out / f"math-quest-2020010{day}-000000.dump").write_bytes(b"old")
    (out / "notes.txt").write_text("keep me")
    (out / "math-quest-manual-copy.dump").write_bytes(b"hand named")
    result = _run(BACKUP, ["--once"], _env(source_db, pw, out, KEEP="3"))
    assert result.returncode == 0, result.stderr
    names = [p.name for p in _dumps(out)]
    assert len(names) == 4
    assert names[0:2] == ["math-quest-20200104-000000.dump", "math-quest-20200105-000000.dump"]
    assert (out / "math-quest-manual-copy.dump").exists()
    assert (out / "notes.txt").read_text() == "keep me"


def test_bad_password_fails_without_partial(source_db: str, tmp_path: Path) -> None:
    pw = _write_password(tmp_path, "definitely-wrong-password")
    out = tmp_path / "backups"
    out.mkdir()
    result = _run(BACKUP, ["--once"], _env(source_db, pw, out))
    assert result.returncode != 0
    assert "pg_dump failed" in result.stderr
    assert list(out.iterdir()) == []
    assert "definitely-wrong-password" not in result.stdout + result.stderr


def test_restore_reproduces_row_counts(source_db: str, target_db: str, tmp_path: Path) -> None:
    pw = _write_password(tmp_path)
    out = tmp_path / "backups"
    out.mkdir()
    assert _run(BACKUP, ["--once"], _env(source_db, pw, out)).returncode == 0
    dump = _dumps(out)[0]
    result = _run(RESTORE, [str(dump)], _env(target_db, pw, out))
    assert result.returncode == 0, result.stderr
    expected = _counts(source_db)
    assert expected == {"public.players": 3, "public.attempts": 7}
    assert _parse_counts(result.stdout) == expected
    assert _counts(target_db) == expected


def test_restore_into_non_empty_needs_force(source_db: str, target_db: str, tmp_path: Path) -> None:
    pw = _write_password(tmp_path)
    out = tmp_path / "backups"
    out.mkdir()
    assert _run(BACKUP, ["--once"], _env(source_db, pw, out)).returncode == 0
    dump = _dumps(out)[0]
    assert _run(RESTORE, [str(dump)], _env(target_db, pw, out)).returncode == 0
    asyncio.run(_run_sql(target_db, ["DELETE FROM attempts", "DELETE FROM players"]))

    refused = _run(RESTORE, [str(dump)], _env(target_db, pw, out))
    assert refused.returncode != 0
    assert "--force" in refused.stderr
    assert _counts(target_db) == {"public.players": 0, "public.attempts": 0}

    forced = _run(RESTORE, ["--force", str(dump)], _env(target_db, pw, out))
    assert forced.returncode == 0, forced.stderr
    assert _counts(target_db) == _counts(source_db)


def test_only_old_partials_are_removed_at_startup(source_db: str, tmp_path: Path) -> None:
    pw = _write_password(tmp_path)
    out = tmp_path / "backups"
    out.mkdir()
    stale = out / "math-quest-20200101-000000.dump.partial"
    fresh = out / "math-quest-20200102-000000.dump.partial"
    stale.write_bytes(b"stale")
    fresh.write_bytes(b"in progress elsewhere")
    old = time.time() - 7 * 3600
    os.utime(stale, (old, old))
    result = _run(BACKUP, ["--once"], _env(source_db, pw, out))
    assert result.returncode == 0, result.stderr
    assert not stale.exists()
    assert fresh.exists()
    assert len(_dumps(out)) == 1


def test_failed_forced_restore_rolls_back(source_db: str, target_db: str, tmp_path: Path) -> None:
    pw = _write_password(tmp_path)
    out = tmp_path / "backups"
    out.mkdir()
    assert _run(BACKUP, ["--once"], _env(source_db, pw, out)).returncode == 0
    dump = _dumps(out)[0]
    assert _run(RESTORE, [str(dump)], _env(target_db, pw, out)).returncode == 0
    # An object outside the dump that depends on a dumped table makes the
    # forced DROP of that table fail after earlier drops have already run.
    asyncio.run(_run_sql(target_db, ["CREATE TABLE extra (pid int REFERENCES players(id))"]))

    result = _run(RESTORE, ["--force", str(dump)], _env(target_db, pw, out))
    assert result.returncode != 0
    assert _counts(target_db) == _counts(source_db)
    # The FK drop runs before the failing drop; it survives only if the restore rolled back.
    constraints = asyncio.run(
        _run_sql(
            target_db,
            ["SELECT count(*) AS c FROM pg_constraint WHERE conname = 'attempts_player_id_fkey'"],
        )
    )
    assert constraints[0]["c"] == 1


def _far_slot() -> str:
    return (datetime.now(UTC) + timedelta(hours=6)).strftime("%H:%M")


def _start_loop(env: dict[str, str], tmp_path: Path) -> tuple[subprocess.Popen[bytes], Path]:
    err = tmp_path / "loop.err"
    proc = subprocess.Popen(
        ["sh", str(BACKUP)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=err.open("wb"),
    )
    return proc, err


def _stop(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _wait_for(predicate: Any, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return bool(predicate())


def test_loop_catches_up_when_no_recent_dump(source_db: str, tmp_path: Path) -> None:
    pw = _write_password(tmp_path)
    out = tmp_path / "backups"
    out.mkdir()
    proc, _ = _start_loop(_env(source_db, pw, out, BACKUP_AT=_far_slot()), tmp_path)
    try:
        assert _wait_for(lambda: len(_dumps(out)) == 1, 30)
        assert proc.poll() is None
    finally:
        _stop(proc)


def test_loop_skips_catch_up_when_dump_is_recent(source_db: str, tmp_path: Path) -> None:
    pw = _write_password(tmp_path)
    out = tmp_path / "backups"
    out.mkdir()
    recent = out / "math-quest-20200101-000000.dump"
    recent.write_bytes(b"recent")
    proc, _ = _start_loop(_env(source_db, pw, out, BACKUP_AT=_far_slot()), tmp_path)
    try:
        time.sleep(4)
        assert proc.poll() is None
        assert _dumps(out) == [recent]
    finally:
        _stop(proc)


def test_loop_survives_a_failed_dump(source_db: str, tmp_path: Path) -> None:
    pw = _write_password(tmp_path, "definitely-wrong-password")
    out = tmp_path / "backups"
    out.mkdir()
    env = _env(source_db, pw, out, BACKUP_AT=_far_slot(), RETRY_SECONDS="60")
    proc, err = _start_loop(env, tmp_path)
    try:
        assert _wait_for(lambda: "pg_dump failed" in err.read_text(), 30)
        time.sleep(1)
        assert proc.poll() is None
        assert list(out.iterdir()) == []
        assert "definitely-wrong-password" not in err.read_text()
    finally:
        _stop(proc)


@pytest.mark.parametrize(
    "bad",
    [
        {"KEEP": "0"},
        {"KEEP": "abc"},
        {"KEEP": "-1"},
        {"BACKUP_AT": "25:00"},
        {"BACKUP_AT": "3:15"},
        {"RETRY_SECONDS": "0"},
        {"RETRY_MAX": "abc"},
    ],
)
def test_invalid_settings_exit_without_dumping(
    bad: dict[str, str], source_db: str, tmp_path: Path
) -> None:
    pw = _write_password(tmp_path)
    out = tmp_path / "backups"
    out.mkdir()
    result = _run(BACKUP, ["--once"], _env(source_db, pw, out, **bad))
    assert result.returncode != 0
    assert "error:" in result.stderr
    assert list(out.iterdir()) == []
