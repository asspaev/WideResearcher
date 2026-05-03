from datetime import datetime, timedelta, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research_schedule import ResearchSchedule, ScheduleStatus

_UNIT_SECONDS = {
    "minutes": 60,
    "hours": 3600,
    "days": 86400,
    "weeks": 604800,
    "months": 2592000,
    "years": 31536000,
}


def _build_interval(value: int, unit: str) -> timedelta:
    return timedelta(seconds=_UNIT_SECONDS.get(unit, 86400) * value)


async def upsert_research_schedule(
    session: AsyncSession,
    research_id: int,
    repeat_type: str,
    repeat_value: int,
    repeat_unit: str,
) -> None:
    """Создаёт или обновляет запись планировщика для исследования."""
    scheduled_at = datetime.now(timezone.utc) + _build_interval(repeat_value, repeat_unit)

    stmt = (
        insert(ResearchSchedule)
        .values(
            research_id=research_id,
            scheduled_at=scheduled_at,
            repeat_type=repeat_type,
            repeat_value=repeat_value,
            repeat_unit=repeat_unit,
            status=ScheduleStatus.PLANNED,
        )
        .on_conflict_do_update(
            index_elements=["research_id"],
            set_={
                "scheduled_at": scheduled_at,
                "repeat_type": repeat_type,
                "repeat_value": repeat_value,
                "repeat_unit": repeat_unit,
                "status": ScheduleStatus.PLANNED,
            },
        )
    )
    await session.execute(stmt)
    await session.commit()


async def get_schedule_by_research_id(
    session: AsyncSession,
    research_id: int,
) -> ResearchSchedule | None:
    """Возвращает запись планировщика по research_id."""
    from sqlalchemy import select

    result = await session.execute(select(ResearchSchedule).where(ResearchSchedule.research_id == research_id))
    return result.scalar_one_or_none()


async def delete_planned_schedule(session: AsyncSession, research_id: int) -> None:
    """Удаляет PLANNED запись планировщика для исследования."""
    from sqlalchemy import delete

    stmt = delete(ResearchSchedule).where(
        ResearchSchedule.research_id == research_id,
        ResearchSchedule.status == ScheduleStatus.PLANNED,
    )
    await session.execute(stmt)
    await session.commit()
