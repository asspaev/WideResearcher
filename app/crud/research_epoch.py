from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ResearchEpoch


async def get_research_epoch(
    session: AsyncSession,
    research_id: int,
    epoch_id: int,
) -> ResearchEpoch | None:
    result = await session.execute(
        select(ResearchEpoch).where(
            ResearchEpoch.research_id == research_id,
            ResearchEpoch.epoch_id == epoch_id,
        )
    )
    return result.scalar_one_or_none()


async def update_research_epoch_keywords(
    session: AsyncSession,
    research_id: int,
    epoch_id: int,
    keywords: list[str],
) -> None:
    """Сохраняет список поисковых запросов в поле research_search_keywords эпохи.

    Args:
        session: Активная сессия БД.
        research_id: ID исследования.
        epoch_id: ID эпохи.
        keywords: Список поисковых запросов.
    """
    epoch = await get_research_epoch(session, research_id, epoch_id)
    if epoch is None:
        return
    epoch.research_search_keywords = keywords
    await session.commit()


async def update_research_epoch_search_links(
    session: AsyncSession,
    research_id: int,
    epoch_id: int,
    links: list[dict],
) -> None:
    """Сохраняет топ-ссылки поиска в поле research_result_search_links эпохи.

    Args:
        session: Активная сессия БД.
        research_id: ID исследования.
        epoch_id: ID эпохи.
        links: Список ссылок с метаданными (title, url, total_score).
    """
    epoch = await get_research_epoch(session, research_id, epoch_id)
    if epoch is None:
        return
    epoch.research_result_search_links = links
    await session.commit()


async def update_research_epoch_body_finish(
    session: AsyncSession,
    research_id: int,
    epoch_id: int,
    body_finish: dict,
) -> None:
    """Сохраняет результат написания статьи в поле research_body_finish эпохи.

    Args:
        session: Активная сессия БД.
        research_id: ID исследования.
        epoch_id: ID эпохи.
        body_finish: Результат исследования (JSONB).
    """
    epoch = await get_research_epoch(session, research_id, epoch_id)
    if epoch is None:
        return
    epoch.research_body_finish = body_finish
    await session.commit()


async def create_research_epoch(
    session: AsyncSession,
    research_id: int,
    epoch_id: int,
    body_start: dict,
    body_finish: dict,
    direction_content: str | None = None,
) -> ResearchEpoch:
    record = ResearchEpoch(
        research_id=research_id,
        epoch_id=epoch_id,
        research_body_start=body_start,
        research_body_finish=body_finish,
        research_direction_content=direction_content,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
