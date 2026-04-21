from app.core.research.base import ResearchStepBase


class SummarizeStepBase(ResearchStepBase):
    """Базовый класс для шага суммаризации."""

    async def execute(self) -> None:
        """Выполняет суммаризацию. Должен быть переопределён в наследниках."""
        pass
