import tiktoken
from loguru import logger
from sqlalchemy.dialects.postgresql import insert

from app.crud.model import get_model_by_id
from app.crud.research import update_research_stage
from app.crud.scrapped_page import get_scrapped_page
from app.models.chunk_summary import ChunkSummary
from app.models.research import RESEARCH_STAGES

from .base import ResearchStepBase

_EMBED_ENCODING = "cl100k_base"


def chunk_text(text: str, max_tokens: int) -> list[str]:
    """Разбивает текст на чанки по количеству токенов.

    Args:
        text: Исходный текст для нарезки.
        max_tokens: Максимальное число токенов в одном чанке.

    Returns:
        Список строк-чанков, каждый не превышает max_tokens токенов.
    """
    enc = tiktoken.get_encoding(_EMBED_ENCODING)
    tokens = enc.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunks.append(enc.decode(tokens[i : i + max_tokens]))
    return chunks


class ChunkingResearchStep(ResearchStepBase):
    """Шаг разбивки страниц на чанки и сохранения их в ChunkSummary."""

    async def execute(self) -> None:
        """Разбивает страницы из research_result_search_links на чанки и сохраняет в БД.

        Для каждой ссылки из research_result_search_links берёт очищенный контент
        ScrappedPage, нарезает его на чанки с учётом model_max_tokens и записывает
        каждый чанк в таблицу chunk_summaries.
        """
        research = self._research

        if not research.research_result_search_links:
            logger.warning(f"{self._log_extra()} ChunkingResearchStep: no search links found, skipping")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SCRAPE"])

        model = await get_model_by_id(self._session, research.model_id_embed)
        if model is None:
            logger.warning(f"{self._log_extra()} ChunkingResearchStep: embed model not found, skipping")
            self.has_error = True
            return

        max_tokens: int = model.model_max_tokens
        links: list[dict] = research.research_result_search_links

        total_chunks = 0
        for link in links:
            url: str = link["url"]
            page = await get_scrapped_page(self._session, url)
            if page is None or not page.page_clean_content:
                logger.debug(f"{self._log_extra()} ChunkingResearchStep: no content for {url!r}, skipping")
                continue

            chunks = chunk_text(page.page_clean_content, max_tokens)
            for idx, chunk_content in enumerate(chunks):
                stmt = (
                    insert(ChunkSummary)
                    .values(
                        page_url=url,
                        research_id=research.research_id,
                        chunk_index=idx,
                        chunk_content=chunk_content,
                    )
                    .on_conflict_do_update(
                        index_elements=["page_url", "research_id", "chunk_index"],
                        set_={"chunk_content": chunk_content},
                    )
                )
                await self._session.execute(stmt)

            total_chunks += len(chunks)
            logger.debug(f"{self._log_extra()} ChunkingResearchStep: {url!r} → {len(chunks)} chunk(s)")

        await self._session.commit()
        logger.info(
            f"{self._log_extra()} ChunkingResearchStep: done " f"(links={len(links)}, total_chunks={total_chunks})"
        )
