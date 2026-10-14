"""Repository for the app_settings key/value table."""

from sqlalchemy.ext.asyncio import AsyncSession

from mathquest.entities.models import AppSetting


async def get_setting(db: AsyncSession, key: str) -> str | None:
    row = await db.get(AppSetting, key)
    return row.value if row else None


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    await db.flush()
