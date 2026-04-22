import math

from loguru import logger

from app.crud.page_summary import get_page_summary, upsert_page_embed_score
from app.crud.research import update_research_embed_links, update_research_embed_summary, update_research_stage
from app.crud.scrapped_page import get_scrapped_page
from app.models.research import RESEARCH_STAGES

from .base import ScoringPagesStepBase

# ~4 символа на токен → 8 000 токенов ≈ 32 000 символов, безопасно до 24 000 чтобы учесть возможные токены в embed-результате и не перегрузить модель
_CHARS_PER_CHUNK = 24_000


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _chunk_text(text: str, chunk_size: int = _CHARS_PER_CHUNK) -> list[str]:
    """Разбивает текст на чанки заданного размера (в символах)."""
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


class EmbedScoringStep(ScoringPagesStepBase):
    """Шаг фильтрации страниц по алгоритму Embed (косинусное сходство)."""

    async def execute(self) -> None:
        """Вычисляет embed-оценки страниц и сохраняет топ-N в research_result_embed_links.

        Получает эмбеддинг саммари исследования (query + direction) — если он уже
        сохранён в research_result_embed_summary, использует кэш. Для каждой страницы
        из research_result_bm25_links аналогично проверяет кэш в PageSummary.page_embed.
        Вычисляет косинусное сходство, сохраняет embed_score и page_embed.
        Топ-N URL записывает в Research.research_result_embed_links.
        """
        research = self._research

        if not research.research_result_bm25_links:
            logger.warning(f"{self._log_extra()} EmbedScoringStep: no bm25 links found, skipping")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["SCORING_EMBED"])

        llm = await self._get_llm(research.model_id_embed)
        if llm is None:
            logger.warning(f"{self._log_extra()} EmbedScoringStep: embed model not found, skipping")
            return

        # Получаем эмбеддинг саммари — берём из кэша если уже есть
        if research.research_result_embed_summary:
            summary_embedding: list[float] = research.research_result_embed_summary
            logger.debug(f"{self._log_extra()} EmbedScoringStep: using cached summary embedding")
        else:
            query: str = (research.research_body_start or {}).get("query", research.research_name)
            direction: str = research.research_direction_content or ""
            summary_text: str = f"{query} {direction}".strip()
            try:
                summary_embedding = await llm.embed(summary_text)
            except Exception as exc:
                logger.error(f"{self._log_extra()} EmbedScoringStep: failed to embed summary: {exc}")
                return
            await update_research_embed_summary(self._session, research, summary_embedding)

        links: list[dict] = research.research_result_bm25_links

        scored: list[tuple[str, float]] = []
        for link in links:
            url: str = link["url"]
            page = await get_scrapped_page(self._session, url)
            if page is None or not page.page_clean_content:
                logger.debug(f"{self._log_extra()} EmbedScoringStep: no content for {url!r}, skipping")
                continue

            # Проверяем кэш эмбеддинга страницы (хранится лучший чанк)
            page_summary = await get_page_summary(self._session, url, research.research_id)
            if page_summary is not None and page_summary.page_embed:
                best_embedding: list[float] = page_summary.page_embed
                best_similarity = _cosine_similarity(summary_embedding, best_embedding)
                logger.debug(f"{self._log_extra()} EmbedScoringStep: using cached page embedding for {url!r}")
            else:
                chunks = _chunk_text(page.page_clean_content)
                best_similarity = -1.0
                best_embedding = []
                for chunk_idx, chunk in enumerate(chunks):
                    try:
                        chunk_embedding = await llm.embed(chunk)
                    except Exception as exc:
                        logger.error(
                            f"{self._log_extra()} EmbedScoringStep: failed to embed chunk {chunk_idx} "
                            f"of {url!r}: {exc}"
                        )
                        continue
                    sim = _cosine_similarity(summary_embedding, chunk_embedding)
                    if sim > best_similarity:
                        best_similarity = sim
                        best_embedding = chunk_embedding
                if not best_embedding:
                    logger.debug(f"{self._log_extra()} EmbedScoringStep: no chunks embedded for {url!r}, skipping")
                    continue
                logger.debug(
                    f"{self._log_extra()} EmbedScoringStep: embedded {len(chunks)} chunk(s) for {url!r}, "
                    f"best_sim={best_similarity:.3f}"
                )

            score = round(max(0.0, min(1.0, best_similarity)), 3)

            try:
                await upsert_page_embed_score(
                    session=self._session,
                    page_url=url,
                    research_id=research.research_id,
                    embed_score=score,
                    page_embed=best_embedding,
                )
                scored.append((url, score))
                logger.debug(f"{self._log_extra()} EmbedScoringStep: scored {url!r} = {score:.3f}")
            except Exception as exc:
                logger.error(f"{self._log_extra()} EmbedScoringStep: failed to save score for {url!r}: {exc}")

        top_n: int = research.settings_n_embed_pages
        top_urls = sorted(scored, key=lambda x: x[1], reverse=True)[:top_n]
        embed_links = [{"url": url, "embed_score": score} for url, score in top_urls]

        await update_research_embed_links(self._session, research, embed_links)
        logger.info(f"{self._log_extra()} EmbedScoringStep: done (scored={len(scored)}, top={len(embed_links)})")
