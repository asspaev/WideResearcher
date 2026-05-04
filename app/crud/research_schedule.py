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
    model_id_answer: int = 0,
    model_id_search: int = 0,
    model_id_direction: int | None = None,
    model_id_embed: int | None = None,
    model_id_reranker: int | None = None,
    settings_n_async_parse: int = 3,
    settings_scenario_type: str = "NORMAL",
    settings_search_areas: str | None = None,
    settings_exclude_search_areas: str | None = None,
    settings_n_vectors: int = 5,
    settings_n_search_queries: int = 5,
    settings_n_top_search_results: int = 10,
    settings_n_top_bm25_chunks: int = 50,
    settings_n_top_embed_chunks: int = 30,
    settings_n_top_rerank_chunks: int = 15,
) -> None:
    """Создаёт или обновляет запись планировщика для исследования."""
    scheduled_at = datetime.now(timezone.utc) + _build_interval(repeat_value, repeat_unit)

    values = {
        "research_id": research_id,
        "scheduled_at": scheduled_at,
        "repeat_type": repeat_type,
        "repeat_value": repeat_value,
        "repeat_unit": repeat_unit,
        "status": ScheduleStatus.PLANNED,
        "model_id_answer": model_id_answer,
        "model_id_search": model_id_search,
        "model_id_direction": model_id_direction,
        "model_id_embed": model_id_embed,
        "model_id_reranker": model_id_reranker,
        "settings_n_async_parse": settings_n_async_parse,
        "settings_scenario_type": settings_scenario_type,
        "settings_search_areas": settings_search_areas,
        "settings_exclude_search_areas": settings_exclude_search_areas,
        "settings_n_vectors": settings_n_vectors,
        "settings_n_search_queries": settings_n_search_queries,
        "settings_n_top_search_results": settings_n_top_search_results,
        "settings_n_top_bm25_chunks": settings_n_top_bm25_chunks,
        "settings_n_top_embed_chunks": settings_n_top_embed_chunks,
        "settings_n_top_rerank_chunks": settings_n_top_rerank_chunks,
    }

    stmt = (
        insert(ResearchSchedule)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["research_id"],
            set_={k: v for k, v in values.items() if k != "research_id"},
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


async def get_due_planned_schedules(session: AsyncSession) -> list[ResearchSchedule]:
    """Возвращает все PLANNED расписания, у которых scheduled_at <= now()."""
    from sqlalchemy import select

    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(ResearchSchedule).where(
            ResearchSchedule.status == ScheduleStatus.PLANNED,
            ResearchSchedule.scheduled_at <= now,
        )
    )
    return list(result.scalars().all())


async def mark_schedule_completed(session: AsyncSession, schedule_id: int) -> None:
    """Переводит запись планировщика в статус COMPLETED."""
    from sqlalchemy import update

    stmt = (
        update(ResearchSchedule)
        .where(ResearchSchedule.schedule_id == schedule_id)
        .values(status=ScheduleStatus.COMPLETED)
    )
    await session.execute(stmt)
    await session.commit()
