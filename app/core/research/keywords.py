import json

from loguru import logger

from app.crud.research import update_research_search_keywords, update_research_stage
from app.models.research import RESEARCH_STAGES, Research
from app.services.prompts import build_search_keywords_messages

from .base import ResearchStepBase


class KeywordsResearchStep(ResearchStepBase):
    """Генерация поисковых запросов для SearXNG."""

    async def execute(self) -> list[str]:
        """Генерирует поисковые запросы на основе темы и направления.

        Returns:
            Список поисковых запросов или пустой список при ошибке.
        """
        # Переключаем стадию исследования на «генерация ключевых слов»
        research: Research = self._research

        # Подтягиваем direction из тела research
        direction = research.research_direction_content or ""
        if not direction:
            logger.error(f"{self._log_extra()} KeywordsResearchStep: direction is empty")
            self.has_error = True
            return []
        await update_research_stage(self._session, research, RESEARCH_STAGES["KEYWORDS"])

        # Получаем LLM-клиент для поискового шага
        llm = await self._get_llm(research.model_id_search)
        if llm is None:
            logger.error(f"{self._log_extra()} KeywordsResearchStep: search model {research.model_id_search} not found")
            self.has_error = True
            return []

        # Формируем сообщения и генерируем ключевые слова через LLM
        messages = build_search_keywords_messages(
            query=research.research_name,
            direction=direction,
            n_keywords=research.settings_n_search_queries,
        )

        keywords: list[str] = []
        try:
            result = await llm.generate(
                messages,
                session=self._session,
                model_id=research.model_id_search,
                research_id=research.research_id,
                step_type="search_keywords",
            )
            # Парсим JSON-массив строк из ответа LLM
            keywords = json.loads(result)
            if not isinstance(keywords, list):
                raise ValueError(f"expected JSON array, got {type(keywords).__name__}")
            keywords = [str(k) for k in keywords]
            logger.info(f"{self._log_extra()} KeywordsResearchStep: generated {len(keywords)} keywords")
        except Exception as exc:
            self.has_error = True
            logger.error(f"{self._log_extra()} KeywordsResearchStep: failed: {exc}")

        # Сохраняем ключевые слова в БД, если они были получены
        if keywords:
            await update_research_search_keywords(
                session=self._session,
                research=research,
                keywords=keywords,
            )
        else:
            logger.error(f"{self._log_extra()} KeywordsResearchStep: no keywords generated")
            self.has_error = True
            return []

        return keywords
