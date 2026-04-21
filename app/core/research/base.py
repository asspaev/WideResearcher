from abc import ABC, abstractmethod

from app.crud.model import get_model_by_id
from app.services.llm_client import LLMClient


class ResearchStepBase(ABC):
    """Абстрактный класс, представляющий шаг исследования."""

    def __init__(self, session, research) -> None:
        self._session = session
        self._research = research
        self.has_error = False

    @abstractmethod
    async def execute(self):
        """Метод для выполнения шага исследования."""
        pass

    def _log_extra(self) -> str:
        """Возвращает префикс для логов с идентификаторами исследования и пользователя."""
        return f"[R={self._research.research_id} U={self._research.user_id}]"

    async def _get_llm(self, model_id) -> LLMClient | None:
        """Возвращает LLMClient для указанной модели или None если модель не найдена.

        Args:
            model_id: ID модели из таблицы models.

        Returns:
            Инициализированный LLMClient или None.
        """
        model = await get_model_by_id(self._session, model_id)
        if model is None:
            return None
        return LLMClient(
            model_name=model.model_api_model,
            base_url=model.model_base_url,
            api_key=model.model_key_api,
        )
