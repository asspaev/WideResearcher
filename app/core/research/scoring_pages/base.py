from app.core.research.base import ResearchStepBase


class ScoringPagesStepBase(ResearchStepBase):
    """Базовый класс для шага оценки страниц."""

    async def execute(self) -> None:
        """Выполняет оценку страниц. Должен быть переопределён в наследниках."""
        pass
