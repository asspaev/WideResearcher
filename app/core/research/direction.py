from loguru import logger

from app.crud.research import update_research_body_start, update_research_direction_content, update_research_stage
from app.models.research import RESEARCH_STAGES, Research
from app.services.prompts import build_direction_messages

from .base import ResearchStepBase


class DirectionStepError(Exception):
    """Ошибка, возникающая при неудачном выполнении DirectionResearchStep."""


class DirectionResearchStep(ResearchStepBase):
    """Определение направления исследования через LLM."""

    async def execute(self) -> str:
        """Определяет направление исследования через LLM.

        Returns:
            Текст направления или пустая строка при ошибке.

        Raises:
            Exception: если LLM-вызов завершился ошибкой.
        """
        # Переключаем стадию исследования на «определение направления»
        research: Research = self._research
        await update_research_stage(self._session, research, RESEARCH_STAGES["DIRECTION"])

        # Записываем начальное тело исследования
        await update_research_body_start(
            session=self._session,
            research=research,
            body_start={"query": research.research_name},
        )

        # Проверяем, назначена ли модель для шага — если нет, пропускаем
        if research.model_id_direction is None:
            logger.warning(f"{self._log_extra()} DirectionResearchStep: no model_id_direction, skipping")
            raise DirectionStepError("model_id_direction is not set")

        # Получаем клиент LLM по идентификатору модели
        llm = await self._get_llm(research.model_id_direction)
        if llm is None:
            logger.error(
                f"{self._log_extra()} DirectionResearchStep: direction model {research.model_id_direction} not found"
            )
            raise DirectionStepError(f"direction model {research.model_id_direction} not found")

        # Формируем сообщения для LLM и запускаем генерацию направления
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

        # Сохраняем результат в БД (содержимое направления)
        await update_research_direction_content(
            session=self._session,
            research=research,
            direction_content=direction_content,
        )

        # Пробрасываем исключение, если генерация завершилась ошибкой
        if raised is not None:
            raise DirectionStepError("LLM generation failed") from raised

        return direction_content or ""
