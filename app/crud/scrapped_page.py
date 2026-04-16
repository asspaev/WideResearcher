"""CRUD-операции для модели ScrappedPage."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scrapped_page import ScrapeStatus, ScrappedPage


async def get_scrapped_page(session: AsyncSession, url: str) -> ScrappedPage | None:
    result = await session.execute(select(ScrappedPage).where(ScrappedPage.page_url == url))
    return result.scalar_one_or_none()


async def upsert_scrapped_page(
    session: AsyncSession,
    url: str,
    raw_content: str,
    clean_content: str | None,
    status: ScrapeStatus,
) -> ScrappedPage:
    """Создаёт или обновляет запись спаршенной страницы.

    Args:
        session: Активная сессия БД.
        url: URL страницы (первичный ключ).
        raw_content: Сырой HTML-контент.
        clean_content: Очищенный текст.
        status: Статус парсинга.

    Returns:
        Созданная или обновлённая запись ScrappedPage.
    """
    existing = await get_scrapped_page(session, url)
    if existing is not None:
        existing.page_raw_content = raw_content
        existing.page_clean_content = clean_content
        existing.page_scrapped_status = status
        await session.commit()
        await session.refresh(existing)
        return existing

    record = ScrappedPage(
        page_url=url,
        page_raw_content=raw_content,
        page_clean_content=clean_content,
        page_scrapped_status=status,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
