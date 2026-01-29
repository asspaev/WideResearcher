from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Model


async def get_models_by_user_id(
    session: AsyncSession,
    user_id: int,
) -> list[Model]:
    """
    Возвращает все модели пользователя по user_id.
    """
    stmt = select(Model).where(Model.user_id == user_id)

    result = await session.execute(stmt)
    return result.scalars().all()
