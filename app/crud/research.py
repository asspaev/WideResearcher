from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Research, ResearchSchedule
from app.models.research_schedule import ScheduleStatus


async def get_all_researches_with_schedules_by_user_id(
    session: AsyncSession,
    user_id: int,
) -> list[tuple[Research, ResearchSchedule | None]]:
    """
    Возвращает все исследования пользователя по user_id вместе с их расписаниями.
    Если расписаний нет, то второй элемент кортежа будет None.
    """
    # LEFT OUTER JOIN
    stmt = (
        select(Research, ResearchSchedule)
        .join(ResearchSchedule, Research.research_id == ResearchSchedule.research_id, isouter=True)
        .where(Research.user_id == user_id)
    )

    result = await session.execute(stmt)
    return result.all()


async def get_next_planned_research_by_user_id(
    session: AsyncSession,
    user_id: int,
) -> tuple[Research | None, ResearchSchedule | None]:
    """
    Возвращает ближайшее исследование пользователя со статусом PLANNED по scheduled_at.
    Если нет такого исследования, возвращает (None, None).
    """
    stmt = (
        select(Research, ResearchSchedule)
        .join(
            ResearchSchedule,
            Research.research_id == ResearchSchedule.research_id,
            isouter=False,  # INNER JOIN, чтобы брать только исследования с расписаниями
        )
        .where(Research.user_id == user_id, ResearchSchedule.status == ScheduleStatus.PLANNED)
        .order_by(asc(ResearchSchedule.scheduled_at))
        .limit(1)  # берём только ближайшее
    )

    result = await session.execute(stmt)
    row = result.first()

    if row is None:
        return None, None

    return row
