"""CRUD-операции для page_summaries."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page_summary import PageSummary


async def upsert_page_summary(
    session: AsyncSession,
    page_url: str,
    research_id: int,
    page_summary: str,
    relevance_score: float | None = None,
) -> None:
    """Создаёт или обновляет саммари страницы для конкретного исследования.

    Args:
        session: Активная сессия БД.
        page_url: URL страницы.
        research_id: Идентификатор исследования.
        page_summary: Текст саммари.
        relevance_score: Оценка релевантности от 0 до 1.0.
    """
    values: dict = {
        "page_url": page_url,
        "research_id": research_id,
        "page_summary": page_summary,
    }
    if relevance_score is not None:
        values["relevance_score"] = relevance_score

    update_fields: dict = {"page_summary": page_summary}
    if relevance_score is not None:
        update_fields["relevance_score"] = relevance_score

    stmt = (
        insert(PageSummary)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["page_url", "research_id"],
            set_=update_fields,
        )
    )
    await session.execute(stmt)
    await session.commit()


async def upsert_page_bm25_score(
    session: AsyncSession,
    page_url: str,
    research_id: int,
    bm25_score: float,
) -> None:
    """Создаёт или обновляет bm25_score страницы для конкретного исследования.

    Args:
        session: Активная сессия БД.
        page_url: URL страницы.
        research_id: Идентификатор исследования.
        bm25_score: BM25-оценка релевантности от 0 до 1.0.
    """
    stmt = (
        insert(PageSummary)
        .values(page_url=page_url, research_id=research_id, bm25_score=bm25_score, page_summary="")
        .on_conflict_do_update(
            index_elements=["page_url", "research_id"],
            set_={"bm25_score": bm25_score},
        )
    )
    await session.execute(stmt)
    await session.commit()


async def upsert_page_embed_score(
    session: AsyncSession,
    page_url: str,
    research_id: int,
    embed_score: float,
    page_embed: list[float] | None = None,
) -> None:
    """Создаёт или обновляет embed_score и page_embed страницы для конкретного исследования.

    Args:
        session: Активная сессия БД.
        page_url: URL страницы.
        research_id: Идентификатор исследования.
        embed_score: Embed-оценка релевантности от 0 до 1.0.
        page_embed: Вектор эмбеддинга страницы.
    """
    values: dict = {
        "page_url": page_url,
        "research_id": research_id,
        "embed_score": embed_score,
        "page_summary": "",
    }
    update_fields: dict = {"embed_score": embed_score}
    if page_embed is not None:
        values["page_embed"] = page_embed
        update_fields["page_embed"] = page_embed

    stmt = (
        insert(PageSummary)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["page_url", "research_id"],
            set_=update_fields,
        )
    )
    await session.execute(stmt)
    await session.commit()


async def upsert_page_rerank_score(
    session: AsyncSession,
    page_url: str,
    research_id: int,
    rerank_score: float,
) -> None:
    """Создаёт или обновляет rerank_score страницы для конкретного исследования.

    Args:
        session: Активная сессия БД.
        page_url: URL страницы.
        research_id: Идентификатор исследования.
        rerank_score: Rerank-оценка релевантности от 0 до 1.0.
    """
    stmt = (
        insert(PageSummary)
        .values(page_url=page_url, research_id=research_id, rerank_score=rerank_score, page_summary="")
        .on_conflict_do_update(
            index_elements=["page_url", "research_id"],
            set_={"rerank_score": rerank_score},
        )
    )
    await session.execute(stmt)
    await session.commit()


async def get_page_summary(
    session: AsyncSession,
    page_url: str,
    research_id: int,
) -> PageSummary | None:
    """Возвращает запись PageSummary по URL страницы и ID исследования.

    Args:
        session: Активная сессия БД.
        page_url: URL страницы.
        research_id: Идентификатор исследования.

    Returns:
        Объект PageSummary или None если не найден.
    """
    stmt = select(PageSummary).where(
        PageSummary.page_url == page_url,
        PageSummary.research_id == research_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_page_summaries_by_research(
    session: AsyncSession,
    research_id: int,
    limit: int | None = None,
) -> list[PageSummary]:
    """Возвращает саммари страниц для указанного исследования.

    Args:
        session: Активная сессия БД.
        research_id: Идентификатор исследования.
        limit: Если указан — возвращает только топ-N записей по убыванию relevance_score.

    Returns:
        Список объектов PageSummary.
    """
    stmt = select(PageSummary).where(PageSummary.research_id == research_id)
    if limit is not None:
        stmt = stmt.order_by(PageSummary.relevance_score.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
