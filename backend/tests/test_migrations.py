from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities import models
from mathquest.shared.db import Base


async def test_models_match_migration(db: AsyncSession) -> None:
    assert models.Player.__tablename__ == "players"

    def diff(sync_conn: Connection) -> list[object]:
        ctx = MigrationContext.configure(sync_conn)
        return list(compare_metadata(ctx, Base.metadata))

    conn = await db.connection()
    assert await conn.run_sync(diff) == []
