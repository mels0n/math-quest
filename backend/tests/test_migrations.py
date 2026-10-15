import asyncio
import uuid

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities import admin, lessons, mastery, models, placement, problems, teaching
from mathquest.shared.db import Base
from tests.conftest import (
    BACKEND_DIR,
    _database_url,  # pyright: ignore[reportPrivateUsage]
    _exec,  # pyright: ignore[reportPrivateUsage]
    _schema_engine,  # pyright: ignore[reportPrivateUsage]
)


async def test_models_match_migration(db: AsyncSession) -> None:
    assert models.Player.__tablename__ == "players"
    assert {
        admin.AdminSession.__tablename__,
        admin.AdminAudit.__tablename__,
        mastery.SkillMastery.__tablename__,
        problems.Attempt.__tablename__,
        lessons.LessonSeen.__tablename__,
        lessons.LessonTry.__tablename__,
        teaching.ExplanationView.__tablename__,
        teaching.StuckEvent.__tablename__,
        placement.PlacementRun.__tablename__,
    } <= set(Base.metadata.tables)

    def diff(sync_conn: Connection) -> list[object]:
        ctx = MigrationContext.configure(sync_conn)
        return list(compare_metadata(ctx, Base.metadata))

    conn = await db.connection()
    assert await conn.run_sync(diff) == []


async def test_existing_problem_rows_default_to_the_bare_variant(db: AsyncSession) -> None:
    columns = await db.execute(
        text(
            "SELECT column_name, is_nullable, column_default FROM information_schema.columns"
            " WHERE table_name = 'problem_instances' AND table_schema = current_schema()"
            " AND column_name IN ('variant', 'template_id') ORDER BY column_name"
        )
    )
    rows = {r[0]: (r[1], r[2]) for r in columns}
    assert rows["template_id"] == ("YES", None)
    nullable, default = rows["variant"]
    assert nullable == "NO"
    assert default is not None and "bare" in default


def _alembic(url: str, schema: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["search_path"] = schema
    return cfg


async def _rows(url: str, schema: str, *statements: str) -> list[tuple[object, ...]]:
    """Run ``statements`` in one transaction; the rows of the last one."""
    engine = _schema_engine(url, schema)
    try:
        async with engine.begin() as conn:
            result = None
            for sql in statements:
                result = await conn.execute(text(sql))
            assert result is not None
            return [tuple(r) for r in result] if result.returns_rows else []
    finally:
        await engine.dispose()


def test_0006_gives_old_rows_the_bare_variant_and_downgrades() -> None:
    url = _database_url()
    schema = f"mq_mig_{uuid.uuid4().hex[:12]}"
    asyncio.run(_exec(url, f'CREATE SCHEMA "{schema}"'))
    try:
        cfg = _alembic(url, schema)
        command.upgrade(cfg, "0005")
        player, session, problem = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        asyncio.run(
            _rows(
                url,
                schema,
                "INSERT INTO players (id, nickname, nickname_key, recovery_hash)"
                f" VALUES ('{player}', 'Old', 'old', 'x')",
                "INSERT INTO play_sessions (id, player_id, mode, started_at)"
                f" VALUES ('{session}', '{player}', 'adventure', now())",
                "INSERT INTO problem_instances"
                " (id, session_id, player_id, skill_id, tier, seed, difficulty, issued_at)"
                f" VALUES ('{problem}', '{session}', '{player}', 'add_within_10',"
                " 0, 7, 0.0, now())",
            )
        )
        command.upgrade(cfg, "0006")
        rows = asyncio.run(_rows(url, schema, "SELECT variant, template_id FROM problem_instances"))
        assert rows == [("bare", None)]
        command.downgrade(cfg, "0005")
        columns = asyncio.run(
            _rows(
                url,
                schema,
                "SELECT column_name FROM information_schema.columns"
                f" WHERE table_schema = '{schema}' AND table_name = 'problem_instances'",
            )
        )
        assert {"variant", "template_id"}.isdisjoint({c[0] for c in columns})
        assert asyncio.run(_rows(url, schema, "SELECT count(*) FROM problem_instances")) == [(1,)]
    finally:
        asyncio.run(_exec(url, f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def test_0007_adds_and_drops_the_lesson_tables() -> None:
    url = _database_url()
    schema = f"mq_mig_{uuid.uuid4().hex[:12]}"
    asyncio.run(_exec(url, f'CREATE SCHEMA "{schema}"'))
    tables = (
        "SELECT table_name FROM information_schema.tables"
        f" WHERE table_schema = '{schema}' AND table_name LIKE 'lesson%' ORDER BY table_name"
    )
    try:
        cfg = _alembic(url, schema)
        command.upgrade(cfg, "0007")
        assert asyncio.run(_rows(url, schema, tables)) == [("lesson_tries",), ("lessons_seen",)]
        command.downgrade(cfg, "0006")
        assert asyncio.run(_rows(url, schema, tables)) == []
    finally:
        asyncio.run(_exec(url, f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def test_0008_adds_help_columns_and_tables_and_downgrades() -> None:
    url = _database_url()
    schema = f"mq_mig_{uuid.uuid4().hex[:12]}"
    asyncio.run(_exec(url, f'CREATE SCHEMA "{schema}"'))
    tables = (
        "SELECT table_name FROM information_schema.tables"
        f" WHERE table_schema = '{schema}'"
        " AND table_name IN ('explanation_views', 'stuck_events') ORDER BY table_name"
    )
    columns = (
        "SELECT column_name FROM information_schema.columns"
        f" WHERE table_schema = '{schema}' AND table_name = 'problem_instances'"
        " AND column_name IN ('hints_used', 'warmup_for') ORDER BY column_name"
    )
    try:
        cfg = _alembic(url, schema)
        command.upgrade(cfg, "0007")
        player, session, problem = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        asyncio.run(
            _rows(
                url,
                schema,
                "INSERT INTO players (id, nickname, nickname_key, recovery_hash)"
                f" VALUES ('{player}', 'Old', 'old', 'x')",
                "INSERT INTO play_sessions (id, player_id, mode, started_at)"
                f" VALUES ('{session}', '{player}', 'adventure', now())",
                "INSERT INTO problem_instances"
                " (id, session_id, player_id, skill_id, tier, seed, difficulty, issued_at)"
                f" VALUES ('{problem}', '{session}', '{player}', 'add_within_10',"
                " 0, 7, 0.0, now())",
            )
        )
        command.upgrade(cfg, "0008")
        assert asyncio.run(_rows(url, schema, tables)) == [
            ("explanation_views",),
            ("stuck_events",),
        ]
        assert asyncio.run(_rows(url, schema, columns)) == [("hints_used",), ("warmup_for",)]
        old = "SELECT hints_used, warmup_for FROM problem_instances"
        assert asyncio.run(_rows(url, schema, old)) == [(0, None)]
        command.downgrade(cfg, "0007")
        assert asyncio.run(_rows(url, schema, tables)) == []
        assert asyncio.run(_rows(url, schema, columns)) == []
    finally:
        asyncio.run(_exec(url, f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def test_0009_adds_placement_and_downgrades_without_provisional_marks() -> None:
    url = _database_url()
    schema = f"mq_mig_{uuid.uuid4().hex[:12]}"
    asyncio.run(_exec(url, f'CREATE SCHEMA "{schema}"'))
    tables = (
        "SELECT table_name FROM information_schema.tables"
        f" WHERE table_schema = '{schema}' AND table_name = 'placement_runs'"
    )
    try:
        cfg = _alembic(url, schema)
        command.upgrade(cfg, "0009")
        assert asyncio.run(_rows(url, schema, tables)) == [("placement_runs",)]
        player = uuid.uuid4()
        rows = asyncio.run(
            _rows(
                url,
                schema,
                "INSERT INTO players (id, nickname, nickname_key, recovery_hash)"
                f" VALUES ('{player}', 'Old', 'old', 'x')",
                "INSERT INTO skill_mastery (player_id, skill_id, state, attempts, review_due_at)"
                f" VALUES ('{player}', 'fresh', 'provisional', 0, now()),"
                f" ('{player}', 'played', 'provisional', 4, now()),"
                f" ('{player}', 'known', 'mastered', 9, now())",
                "SELECT skill_id, placed FROM skill_mastery ORDER BY skill_id",
            )
        )
        assert rows == [("fresh", False), ("known", False), ("played", False)]
        command.downgrade(cfg, "0008")
        assert asyncio.run(_rows(url, schema, tables)) == []
        left = asyncio.run(
            _rows(
                url,
                schema,
                "SELECT skill_id, state, review_due_at IS NULL FROM skill_mastery"
                " ORDER BY skill_id",
            )
        )
        assert left == [("known", "mastered", False), ("played", "learning", True)]
    finally:
        asyncio.run(_exec(url, f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
