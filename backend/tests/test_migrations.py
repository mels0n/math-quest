from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities import admin, mastery, models, problems
from mathquest.shared.db import Base


async def test_models_match_migration(db: AsyncSession) -> None:
    assert models.Player.__tablename__ == "players"
    assert {
        admin.AdminSession.__tablename__,
        admin.AdminAudit.__tablename__,
        mastery.SkillMastery.__tablename__,
        problems.Attempt.__tablename__,
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
