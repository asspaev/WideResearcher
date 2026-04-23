from abc import ABC, abstractmethod

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.research.write.base import WriteStepBase
from app.core.research.write.normal import NormalWriteStep
from app.crud.research import update_research_error, update_research_status
from app.models.research import Research, ResearchStatus

WRITE_MAP: dict[str, type[WriteStepBase]] = {
    "NORMAL": NormalWriteStep,
}


class ScenarioBase(ABC):
    """Абстрактный класс, представляющий сценарий исследования"""

    def __init__(
        self,
        session: AsyncSession,
        research: Research,
        prompt: str,
    ):
        """Инициализирует базовый сценарий исследования."""
        self.session = session
        self.research = research
        self.prompt = prompt

    async def launch(self):
        """Метод для запуска сценария исследования"""
        try:
            await self.pipeline()
            await update_research_status(self.session, self.research, ResearchStatus.COMPLETE)
        except Exception as e:
            logger.error(f"Error in scenario: {e}")
            await update_research_error(self.session, self.research, str(e))

    def get_write_step(self) -> WriteStepBase:
        """Возвращает экземпляр шага написания ответа по полю settings_scenario_type.

        Returns:
            Инициализированный шаг написания ответа.

        Raises:
            ValueError: Если тип шага написания не найден в WRITE_MAP.
        """
        key = self.research.settings_scenario_type.upper()
        cls = WRITE_MAP.get(key)

        if cls is None:
            raise ValueError(f"Unknown write type: {key!r}. Available: {list(WRITE_MAP)}")

        return cls(self.session, self.research)

    @abstractmethod
    async def pipeline(self):
        """Метод, который должен быть реализован в каждом конкретном сценарии исследования"""
        pass
