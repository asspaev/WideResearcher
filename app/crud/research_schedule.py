from datetime import datetime, timedelta, timezone

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
    """Создаёт или обновляет PLANNED запись планировщика для исследования."""
    from sqlalchemy import select, update

    scheduled_at = datetime.now(timezone.utc) + _build_interval(repeat_value, repeat_unit)

    result = await session.execute(
        select(ResearchSchedule)
        .where(
            ResearchSchedule.research_id == research_id,
            ResearchSchedule.status == ScheduleStatus.PLANNED,
        )
        .limit(1)
    )
    existing: ResearchSchedule | None = result.scalar_one_or_none()

    if existing is not None:
        await session.execute(
            update(ResearchSchedule)
            .where(ResearchSchedule.schedule_id == existing.schedule_id)
            .values(
                scheduled_at=scheduled_at,
                repeat_type=repeat_type,
                repeat_value=repeat_value,
                repeat_unit=repeat_unit,
                model_id_answer=model_id_answer,
                model_id_search=model_id_search,
                model_id_direction=model_id_direction,
                model_id_embed=model_id_embed,
                model_id_reranker=model_id_reranker,
                settings_n_async_parse=settings_n_async_parse,
                settings_scenario_type=settings_scenario_type,
                settings_search_areas=settings_search_areas,
                settings_exclude_search_areas=settings_exclude_search_areas,
                settings_n_vectors=settings_n_vectors,
                settings_n_search_queries=settings_n_search_queries,
                settings_n_top_search_results=settings_n_top_search_results,
                settings_n_top_bm25_chunks=settings_n_top_bm25_chunks,
                settings_n_top_embed_chunks=settings_n_top_embed_chunks,
                settings_n_top_rerank_chunks=settings_n_top_rerank_chunks,
            )
        )
    else:
        session.add(
            ResearchSchedule(
                research_id=research_id,
                scheduled_at=scheduled_at,
                repeat_type=repeat_type,
                repeat_value=repeat_value,
                repeat_unit=repeat_unit,
                status=ScheduleStatus.PLANNED,
                model_id_answer=model_id_answer,
                model_id_search=model_id_search,
                model_id_direction=model_id_direction,
                model_id_embed=model_id_embed,
                model_id_reranker=model_id_reranker,
                settings_n_async_parse=settings_n_async_parse,
                settings_scenario_type=settings_scenario_type,
                settings_search_areas=settings_search_areas,
                settings_exclude_search_areas=settings_exclude_search_areas,
                settings_n_vectors=settings_n_vectors,
                settings_n_search_queries=settings_n_search_queries,
                settings_n_top_search_results=settings_n_top_search_results,
                settings_n_top_bm25_chunks=settings_n_top_bm25_chunks,
                settings_n_top_embed_chunks=settings_n_top_embed_chunks,
                settings_n_top_rerank_chunks=settings_n_top_rerank_chunks,
            )
        )

    await session.commit()


async def get_schedule_by_research_id(
    session: AsyncSession,
    research_id: int,
) -> ResearchSchedule | None:
    """Возвращает PLANNED запись планировщика по research_id."""
    from sqlalchemy import select

    result = await session.execute(
        select(ResearchSchedule)
        .where(
            ResearchSchedule.research_id == research_id,
            ResearchSchedule.status == ScheduleStatus.PLANNED,
        )
        .limit(1)
    )
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


async def create_scheduled_run(
    session: AsyncSession,
    schedule: ResearchSchedule,
    original: "Research",
) -> "Research":
    """Создаёт дочернее исследование для планового запуска.

    Args:
        schedule: Запись планировщика с настройками и типом.
        original: Оригинальное исследование (schedule.research_id).

    Returns:
        Только что созданное исследование, готовое к запуску.
    """
    from sqlalchemy import update

    from app.crud.research import create_research
    from app.models.research import Research

    if schedule.repeat_type == "start":
        parent_id = None
    elif schedule.repeat_type == "current":
        parent_id = original.research_id
    else:  # deep
        parent_id = schedule.research_parent_id or original.research_id

    type_label = {"start": "с нуля", "current": "продолжение", "deep": "в глубину"}.get(
        schedule.repeat_type, schedule.repeat_type
    )

    new_research = await create_research(
        session,
        user_id=original.user_id,
        research_name=original.research_name,
        research_version_name=f"Авто ({type_label})",
        model_id_answer=schedule.model_id_answer,
        model_id_search=schedule.model_id_search,
        model_id_direction=schedule.model_id_direction,
        model_id_embed=schedule.model_id_embed,
        model_id_reranker=schedule.model_id_reranker,
        research_parent_id=parent_id,
        research_body_start=original.research_body_start,
        settings_n_async_parse=schedule.settings_n_async_parse,
        settings_scenario_type=schedule.settings_scenario_type,
        settings_search_areas=schedule.settings_search_areas,
        settings_exclude_search_areas=schedule.settings_exclude_search_areas,
        settings_n_vectors=schedule.settings_n_vectors,
        settings_n_search_queries=schedule.settings_n_search_queries,
        settings_n_top_search_results=schedule.settings_n_top_search_results,
        settings_n_top_bm25_chunks=schedule.settings_n_top_bm25_chunks,
        settings_n_top_embed_chunks=schedule.settings_n_top_embed_chunks,
        settings_n_top_rerank_chunks=schedule.settings_n_top_rerank_chunks,
    )

    if schedule.repeat_type == "deep":
        await session.execute(
            update(ResearchSchedule)
            .where(ResearchSchedule.schedule_id == schedule.schedule_id)
            .values(research_parent_id=new_research.research_id)
        )
        await session.commit()
        schedule.research_parent_id = new_research.research_id

    return new_research


async def reschedule_next(session: AsyncSession, schedule: ResearchSchedule) -> None:
    """Завершает текущую запись (COMPLETED) и вставляет новую PLANNED запись."""
    from sqlalchemy import update

    next_at = datetime.now(timezone.utc) + _build_interval(schedule.repeat_value, schedule.repeat_unit)

    await session.execute(
        update(ResearchSchedule)
        .where(ResearchSchedule.schedule_id == schedule.schedule_id)
        .values(status=ScheduleStatus.COMPLETED)
    )

    session.add(
        ResearchSchedule(
            research_id=schedule.research_id,
            scheduled_at=next_at,
            repeat_type=schedule.repeat_type,
            repeat_value=schedule.repeat_value,
            repeat_unit=schedule.repeat_unit,
            status=ScheduleStatus.PLANNED,
            research_parent_id=schedule.research_parent_id,
            model_id_answer=schedule.model_id_answer,
            model_id_search=schedule.model_id_search,
            model_id_direction=schedule.model_id_direction,
            model_id_embed=schedule.model_id_embed,
            model_id_reranker=schedule.model_id_reranker,
            settings_n_async_parse=schedule.settings_n_async_parse,
            settings_scenario_type=schedule.settings_scenario_type,
            settings_search_areas=schedule.settings_search_areas,
            settings_exclude_search_areas=schedule.settings_exclude_search_areas,
            settings_n_vectors=schedule.settings_n_vectors,
            settings_n_search_queries=schedule.settings_n_search_queries,
            settings_n_top_search_results=schedule.settings_n_top_search_results,
            settings_n_top_bm25_chunks=schedule.settings_n_top_bm25_chunks,
            settings_n_top_embed_chunks=schedule.settings_n_top_embed_chunks,
            settings_n_top_rerank_chunks=schedule.settings_n_top_rerank_chunks,
            settings_n_top_chunks=schedule.settings_n_top_chunks,
        )
    )
    await session.commit()
