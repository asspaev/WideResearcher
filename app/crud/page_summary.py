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
) -> None:
    """Создаёт или обновляет саммари страницы для конкретного исследования.

    Args:
        session: Активная сессия БД.
        page_url: URL страницы.
        research_id: Идентификатор исследования.
        page_summary: Текст саммари.
    """
    stmt = (
        insert(PageSummary)
        .values(
            page_url=page_url,
            research_id=research_id,
            page_summary=page_summary,
        )
        .on_conflict_do_update(
            index_elements=["page_url", "research_id"],
            set_={"page_summary": page_summary},
        )
    )
    await session.execute(stmt)
    await session.commit()


async def get_page_summaries_by_research(
    session: AsyncSession,
    research_id: int,
) -> list[PageSummary]:
    """Возвращает все саммари страниц для указанного исследования.

    Args:
        session: Активная сессия БД.
        research_id: Идентификатор исследования.

    Returns:
        Список объектов PageSummary.
    """
    result = await session.execute(select(PageSummary).where(PageSummary.research_id == research_id))
    return list(result.scalars().all())
