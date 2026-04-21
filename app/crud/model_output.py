import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelOutput
from app.models.model_output import ModelResponseStatus


async def create_model_output(
    session: AsyncSession,
    model_id: int,
    research_id: int,
    step_type: str,
    model_input: dict,
    model_output: dict,
    response_status: ModelResponseStatus = ModelResponseStatus.COMPLETE,
    error_body: str | None = None,
) -> ModelOutput:
    record = ModelOutput(
        model_id=model_id,
        research_id=research_id,
        response_status=response_status,
        step_type=step_type,
        model_input=model_input,
        model_output=model_output,
        error_body=error_body,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def update_model_output(
    session: AsyncSession,
    response_id: int,
    response_status: ModelResponseStatus,
    model_output: dict,
    error_body: str | None = None,
) -> None:
    """Обновляет статус, выходные данные и тело ошибки записи model_output.

    Args:
        session: Асинхронная сессия БД.
        response_id: Идентификатор записи.
        response_status: Новый статус (COMPLETE или ERROR).
        model_output: Выходные данные модели.
        error_body: Текст ошибки (заполняется при response_status=ERROR).
    """
    stmt = (
        sa.update(ModelOutput)
        .where(ModelOutput.response_id == response_id)
        .values(
            response_status=response_status,
            model_output=model_output,
            error_body=error_body,
        )
    )
    await session.execute(stmt)
    await session.commit()


async def count_model_outputs_by_model_id(
    session: AsyncSession,
    model_id: int,
) -> int:
    """Возвращает количество записей в model_outputs по model_id."""
    stmt = select(func.count(ModelOutput.response_id)).where(ModelOutput.model_id == model_id)
    result = await session.execute(stmt)
    return result.scalar_one()
