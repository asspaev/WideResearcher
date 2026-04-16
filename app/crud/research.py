from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Research, ResearchSchedule
from app.models.research import RESEARCH_STAGES, ResearchStatus
from app.models.research_schedule import ScheduleStatus


async def create_research(
    session: AsyncSession,
    user_id: int,
    research_name: str,
    research_version_name: str,
    settings_epochs_count: int,
    model_id_answer: int,
    model_id_search: int,
    model_id_direction: int | None = None,
    research_parent_id: int | None = None,
) -> Research:
    research = Research(
        user_id=user_id,
        research_status=ResearchStatus.IN_PROCESS,
        research_stage=RESEARCH_STAGES["LAUNCH"],
        research_name=research_name,
        research_version_name=research_version_name,
        settings_epochs_count=settings_epochs_count,
        model_id_answer=model_id_answer,
        model_id_search=model_id_search,
        model_id_direction=model_id_direction,
        research_parent_id=research_parent_id,
    )
    session.add(research)
    await session.commit()
    await session.refresh(research)
    return research


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


async def update_research_stage(
    session: AsyncSession,
    research: Research,
    stage: str,
) -> None:
    research.research_stage = stage
    await session.commit()


async def get_research_by_id(
    session: AsyncSession,
    research_id: int,
) -> Research | None:
    stmt = select(Research).where(Research.research_id == research_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_research_by_id_and_user_id(
    session: AsyncSession,
    research_id: int,
    user_id: int,
) -> Research | None:
    stmt = select(Research).where(Research.research_id == research_id, Research.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


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
