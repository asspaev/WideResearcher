from loguru import logger
from sqlalchemy import select

from app.crud.research import update_research_body_finish, update_research_stage
from app.models.chunk_summary import ChunkSummary
from app.models.research import RESEARCH_STAGES
from app.services.prompts import build_write_normal_messages, build_write_question_messages

from .base import WriteStepBase
from .segments import format_as_segments


class StandardWriteStep(WriteStepBase):
    """Шаг написания ответа в обычном режиме — одним запросом к LLM."""

    async def execute(self) -> None:
        """Выполняет написание ответа в обычном режиме.

        Генерирует развёрнутый Markdown-ответ за один LLM-вызов,
        конвертирует его в типизированные сегменты и сохраняет в БД.
        """
        research = self._research
        await update_research_stage(self._session, research, RESEARCH_STAGES["WRITE"])

        llm = await self._get_llm(research.model_id_answer)
        if llm is None:
            logger.error(f"{self._log_extra()} StandardWriteStep: answer model {research.model_id_answer} not found")
            self.has_error = True
            return

        rerank_chunks: list[dict] = research.research_result_rerank_chunks or []
        chunk_ids = [c["chunk_id"] for c in rerank_chunks]
        if chunk_ids:
            result = await self._session.execute(select(ChunkSummary).where(ChunkSummary.chunk_id.in_(chunk_ids)))
            chunks_by_id: dict[int, ChunkSummary] = {c.chunk_id: c for c in result.scalars().all()}
        else:
            chunks_by_id = {}

        summaries: list[dict] = [
            {"url": chunk.page_url, "summary": chunk.page_summary}
            for item in rerank_chunks
            if (chunk := chunks_by_id.get(item["chunk_id"])) and chunk.page_summary
        ]

        query: str = (research.research_body_start or {}).get("query", research.research_name)
        direction: str = research.research_direction_content or ""

        scenario_type = (research.settings_scenario_type or "NORMAL").upper()
        if scenario_type == "QUESTION":
            messages = build_write_question_messages(
                query=query,
                summaries=summaries,
            )
            step_type = "write_question"
        else:
            messages = build_write_normal_messages(
                query=query,
                direction=direction,
                summaries=summaries,
            )
            step_type = "write_normal"

        try:
            article_text = await llm.generate(
                messages,
                session=self._session,
                model_id=research.model_id_answer,
                research_id=research.research_id,
                step_type=step_type,
            )
            logger.info(f"{self._log_extra()} StandardWriteStep: article generated ({len(article_text)} chars)")
        except Exception as exc:
            self.has_error = True
            logger.exception(f"{self._log_extra()} StandardWriteStep: generation failed: {exc}")
            return

        segments = format_as_segments(article_text)

        if segments:
            await update_research_body_finish(
                session=self._session,
                research=research,
                body_finish={"segments": segments},
            )
            logger.info(f"{self._log_extra()} StandardWriteStep: done ({len(segments)} segments)")
        else:
            self.has_error = True
            logger.error(f"{self._log_extra()} StandardWriteStep: no segments produced")
