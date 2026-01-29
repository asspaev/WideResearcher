from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelOutput


async def count_model_outputs_by_model_id(
    session: AsyncSession,
    model_id: int,
) -> int:
    """
    Возвращает количество записей в model_outputs по model_id.
    """
    stmt = select(func.count(ModelOutput.response_id)).where(ModelOutput.model_id == model_id)

    result = await session.execute(stmt)
    return result.scalar_one()
