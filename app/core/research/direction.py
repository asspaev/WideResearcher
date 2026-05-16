import re

from loguru import logger

from app.crud.research import (
    get_research_by_id,
    update_research_body_start,
    update_research_direction_content,
    update_research_stage,
)
from app.models.research import RESEARCH_STAGES, Research
from app.services.llm_client import LLMClient, LLMGenerationError
from app.services.prompts import (
    build_direction_continuation_messages,
    build_direction_messages,
    build_segment_summarize_messages,
)

from .base import ResearchStepBase


class DirectionStepError(Exception):
    """Ошибка, возникающая при неудачном выполнении DirectionResearchStep."""


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _format_segment_for_prompt(segment: dict) -> str:
    """Форматирует сегмент для LLM-суммаризации с учётом оценок пользователя.

    Args:
        segment: Словарь с полями type, content, is_like, is_dislike, comment.

    Returns:
        Отформатированная строка или пустая строка если контент пустой.
    """
    content = _strip_html(segment.get("content", "")).strip()
    if not content:
        return ""

    lines = [content]
    if segment.get("is_like"):
        lines.append("[!!!] ПОЛЬЗОВАТЕЛЬ ОТМЕТИЛ КАК ВАЖНОЕ И ПОЛЕЗНОЕ — это направление особенно ценно")
    if segment.get("is_dislike"):
        lines.append("[!!!] ПОЛЬЗОВАТЕЛЬ ОТМЕТИЛ КАК НЕЖЕЛАТЕЛЬНОЕ — избегай этого направления")
    comment = segment.get("comment")
    if comment and str(comment).strip():
        lines.append(f"[Комментарий пользователя]: {str(comment).strip()}")

    return "\n".join(lines)


class DirectionResearchStep(ResearchStepBase):
    """Определение направления исследования через LLM."""

    async def _summarize_parent_segments(self, llm: LLMClient, parent_research) -> str:
        """Суммаризирует сегменты предыдущего исследования в bullet-points.

        Все запросы выполняются параллельно с конкурентностью ``model.model_n_async``.
        Шаг ждёт завершения всех суммаризаций до того, как вернуть результат.

        Args:
            llm: Клиент LLM для генерации суммаризаций.
            parent_research: ORM-объект родительского исследования.

        Returns:
            Строка с объединёнными bullet-point суммари всех сегментов.

        Raises:
            DirectionStepError: Если подряд (по исходному порядку сегментов) пришло
                5 и более ошибок — это означает, что модель/API недоступны.
        """
        segments = (parent_research.research_body_finish or {}).get("segments", [])
        if not segments:
            return ""

        query: str = parent_research.research_name

        formatted_segments: list[str] = []
        for segment in segments:
            formatted = _format_segment_for_prompt(segment)
            if formatted:
                formatted_segments.append(formatted)

        if not formatted_segments:
            return ""

        contexts = [build_segment_summarize_messages(segment_text=text, query=query) for text in formatted_segments]
        results = await llm.generate_many(
            contexts=contexts,
            model_id=self._research.model_id_direction,
            research_id=self._research.research_id,
            step_type="direction_prev_summarize",
        )

        bullet_summaries: list[str] = []
        consecutive_errors = 0
        last_error: LLMGenerationError | None = None
        for summary in results:
            if isinstance(summary, LLMGenerationError):
                consecutive_errors += 1
                last_error = summary
                logger.warning(
                    f"{self._log_extra()} DirectionResearchStep: failed to summarize segment "
                    f"({consecutive_errors}/5): {summary}"
                )
                if consecutive_errors >= 5:
                    raise DirectionStepError("Too many consecutive segment summarization failures") from last_error
                continue
            consecutive_errors = 0
            if summary and summary.strip():
                bullet_summaries.append(summary.strip())

        return "\n\n".join(bullet_summaries)

    async def execute(self) -> str:
        """Определяет направление исследования через LLM.

        Если исследование является продолжением (research_parent_id задан), сначала суммаризирует
        сегменты предыдущего исследования и строит направление с учётом этого контекста.

        Returns:
            Текст направления или пустая строка при ошибке.

        Raises:
            DirectionStepError: если модель не найдена или генерация завершилась ошибкой.
        """
        research: Research = self._research
        await update_research_stage(self._session, research, RESEARCH_STAGES["DIRECTION"])

        await update_research_body_start(
            session=self._session,
            research=research,
            body_start={"query": research.research_name},
        )

        if research.model_id_direction is None:
            logger.warning(f"{self._log_extra()} DirectionResearchStep: no model_id_direction, skipping")
            raise DirectionStepError("model_id_direction is not set")

        llm = await self._get_llm(research.model_id_direction)
        if llm is None:
            logger.error(
                f"{self._log_extra()} DirectionResearchStep: direction model {research.model_id_direction} not found"
            )
            raise DirectionStepError(f"direction model {research.model_id_direction} not found")

        if research.research_parent_id is not None:
            parent = await get_research_by_id(self._session, research.research_parent_id, include_archived=True)
            prev_context = ""
            if parent and parent.research_body_finish:
                logger.info(
                    f"{self._log_extra()} DirectionResearchStep: summarizing parent research "
                    f"R={research.research_parent_id} segments"
                )
                prev_context = await self._summarize_parent_segments(llm, parent)
            messages = build_direction_continuation_messages(
                query=research.research_name,
                n_vectors=research.settings_n_vectors,
                prev_context=prev_context,
            )
        else:
            messages = build_direction_messages(query=research.research_name, n_vectors=research.settings_n_vectors)

        direction_content: str | None = None
        raised: Exception | None = None
        try:
            direction_content = await llm.generate(
                messages,
                session=self._session,
                model_id=research.model_id_direction,
                research_id=research.research_id,
                step_type="direction_brainstorm",
            )
            logger.info(f"{self._log_extra()} DirectionResearchStep: done")
        except Exception as exc:
            raised = exc
            logger.exception(f"{self._log_extra()} DirectionResearchStep: failed: {exc}")

        await update_research_direction_content(
            session=self._session,
            research=research,
            direction_content=direction_content,
        )

        if raised is not None:
            raise DirectionStepError("LLM generation failed") from raised

        return direction_content or ""
