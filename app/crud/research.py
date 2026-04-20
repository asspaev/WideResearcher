from datetime import datetime, timezone

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Research, ResearchSchedule
from app.models.research import RESEARCH_STAGES, ResearchStatus
from app.models.research_schedule import ScheduleStatus


async def get_planned_schedule_by_research_id(
    session: AsyncSession,
    research_id: int,
) -> ResearchSchedule | None:
    """Возвращает ближайшее PLANNED расписание для указанного исследования."""
    stmt = (
        select(ResearchSchedule)
        .where(
            ResearchSchedule.research_id == research_id,
            ResearchSchedule.status == ScheduleStatus.PLANNED,
        )
        .order_by(asc(ResearchSchedule.scheduled_at))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


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
    include_archived: bool = False,
) -> list[tuple[Research, ResearchSchedule | None]]:
    """
    Возвращает все исследования пользователя по user_id вместе с их расписаниями.
    Если расписаний нет, то второй элемент кортежа будет None.

    Args:
        include_archived: Если False (по умолчанию), исключает архивированные исследования.
    """
    # LEFT OUTER JOIN
    stmt = (
        select(Research, ResearchSchedule)
        .join(ResearchSchedule, Research.research_id == ResearchSchedule.research_id, isouter=True)
        .where(Research.user_id == user_id)
    )

    if not include_archived:
        stmt = stmt.where(Research.archived_at.is_(None))

    stmt = stmt.order_by(desc(Research.meta_updated_at))

    result = await session.execute(stmt)
    return result.all()


async def update_research_stage(
    session: AsyncSession,
    research: Research,
    stage: str,
) -> None:
    research.research_stage = stage
    await session.commit()


async def update_research_status(
    session: AsyncSession,
    research: Research,
    status: ResearchStatus,
) -> None:
    research.research_status = status
    await session.commit()


async def get_research_by_id(
    session: AsyncSession,
    research_id: int,
    include_archived: bool = False,
) -> Research | None:
    stmt = select(Research).where(Research.research_id == research_id)

    if not include_archived:
        stmt = stmt.where(Research.archived_at.is_(None))

    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_research_by_id_and_user_id(
    session: AsyncSession,
    research_id: int,
    user_id: int,
    include_archived: bool = False,
) -> Research | None:
    stmt = select(Research).where(Research.research_id == research_id, Research.user_id == user_id)

    if not include_archived:
        stmt = stmt.where(Research.archived_at.is_(None))

    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_next_planned_research_by_user_id(
    session: AsyncSession,
    user_id: int,
    include_archived: bool = False,
) -> tuple[Research | None, ResearchSchedule | None]:
    """
    Возвращает ближайшее исследование пользователя со статусом PLANNED по scheduled_at.
    Если нет такого исследования, возвращает (None, None).

    Args:
        include_archived: Если False (по умолчанию), исключает архивированные исследования.
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

    if not include_archived:
        stmt = stmt.where(Research.archived_at.is_(None))

    result = await session.execute(stmt)
    row = result.first()

    if row is None:
        return None, None

    return row


async def update_research_name(
    session: AsyncSession,
    research_id: int,
    research_name: str,
) -> Research | None:
    """Обновляет название исследования по research_id."""
    result = await session.execute(select(Research).where(Research.research_id == research_id))
    research: Research | None = result.scalar_one_or_none()

    if research is None:
        return None

    research.research_name = research_name
    await session.commit()
    await session.refresh(research)
    return research


async def archive_research(
    session: AsyncSession,
    research_id: int,
) -> bool:
    """
    Архивирует исследование по research_id (устанавливает archived_at = now()).
    Возвращает True, если исследование найдено и архивировано, False если не найдено.
    """
    result = await session.execute(select(Research).where(Research.research_id == research_id))
    research: Research | None = result.scalar_one_or_none()

    if research is None:
        return False

    research.archived_at = datetime.now(timezone.utc)
    await session.commit()
    return True
