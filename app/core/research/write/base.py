from app.core.research.base import ResearchStepBase


class WriteStepBase(ResearchStepBase):
    """Базовый класс для шага написания ответа."""

    async def execute(self) -> None:
        """Выполняет написание ответа. Должен быть переопределён в наследниках."""
        pass
