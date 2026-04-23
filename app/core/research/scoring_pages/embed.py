import math

from loguru import logger
from sqlalchemy import select

from app.crud.research import update_research_embed_chunks, update_research_embed_summary, update_research_stage
from app.models.chunk_summary import ChunkSummary
from app.models.research import RESEARCH_STAGES

from .base import ScoringPagesStepBase


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbedScoringStep(ScoringPagesStepBase):
    """Шаг фильтрации чанков по алгоритму Embed (косинусное сходство)."""

    async def execute(self) -> None:
        """Вычисляет embed-оценки чанков и сохраняет топ-N в research_result_embed_chunks.

        Получает эмбеддинг саммари исследования (query + direction) — если он уже
        сохранён в research_result_embed_summary, использует кэш. Для каждого чанка
        из research_result_bm25_chunks аналогично проверяет кэш в ChunkSummary.page_embed.
        Вычисляет косинусное сходство, сохраняет embed_score и page_embed.
        Топ-N чанков записывает в Research.research_result_embed_chunks.
        """
        research = self._research

        if not research.research_result_bm25_chunks:
            logger.warning(f"{self._log_extra()} EmbedScoringStep: no bm25 chunks found, skipping")
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
                summary_embedding = await llm.embed(
                    summary_text,
                    session=self._session,
                    model_id=research.model_id_embed,
                    research_id=research.research_id,
                    step_type="embed_summary",
                )
            except Exception as exc:
                logger.error(f"{self._log_extra()} EmbedScoringStep: failed to embed summary: {exc}")
                return
            await update_research_embed_summary(self._session, research, summary_embedding)

        bm25_chunks: list[dict] = research.research_result_bm25_chunks
        chunk_ids = [c["chunk_id"] for c in bm25_chunks]

        result = await self._session.execute(select(ChunkSummary).where(ChunkSummary.chunk_id.in_(chunk_ids)))
        chunks_by_id: dict[int, ChunkSummary] = {c.chunk_id: c for c in result.scalars().all()}

        scored: list[tuple[int, str, int, float]] = []
        for item in bm25_chunks:
            chunk_id: int = item["chunk_id"]
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                logger.debug(f"{self._log_extra()} EmbedScoringStep: chunk_id={chunk_id} not found, skipping")
                continue

            if chunk.page_embed:
                embedding: list[float] = chunk.page_embed
                logger.debug(f"{self._log_extra()} EmbedScoringStep: using cached embed for chunk_id={chunk_id}")
            else:
                try:
                    embedding = await llm.embed(
                        chunk.chunk_content,
                        session=self._session,
                        model_id=research.model_id_embed,
                        research_id=research.research_id,
                        step_type="embed_chunk",
                    )
                except Exception as exc:
                    logger.error(f"{self._log_extra()} EmbedScoringStep: failed to embed chunk_id={chunk_id}: {exc}")
                    continue
                chunk.page_embed = embedding

            score = round(max(0.0, min(1.0, _cosine_similarity(summary_embedding, embedding))), 3)
            chunk.embed_score = score
            scored.append((chunk.chunk_id, chunk.page_url, chunk.chunk_index, score))
            logger.debug(f"{self._log_extra()} EmbedScoringStep: chunk_id={chunk_id} score={score:.3f}")

        await self._session.commit()

        top_n: int = research.settings_n_top_embed_chunks
        top_chunks = [
            {
                "chunk_id": chunk_id,
                "page_url": page_url,
                "chunk_index": chunk_index,
                "embed_score": score,
            }
            for chunk_id, page_url, chunk_index, score in sorted(scored, key=lambda x: x[3], reverse=True)[:top_n]
        ]

        await update_research_embed_chunks(self._session, research, top_chunks)
        logger.info(f"{self._log_extra()} EmbedScoringStep: done (scored={len(scored)}, top={len(top_chunks)})")
