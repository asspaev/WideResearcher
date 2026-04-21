from sqlalchemy.ext.asyncio import AsyncSession

from app.core.research import DirectionResearchStep, KeywordsResearchStep, SearchResearchStep
from app.core.research.write import NormalWriteStep
from app.models.research import Research

from .base import ScenarioBase


class NormalScenario(ScenarioBase):

    def __init__(
        self,
        session: AsyncSession,
        research: Research,
        prompt: str,
    ):
        super().__init__(session, research, prompt)
        self.prompt = prompt
        self.direction_step = DirectionResearchStep(session, research)
        self.keywords_step = KeywordsResearchStep(session, research)
        self.search_step = SearchResearchStep(session, research)
        self.summarize_step = self.get_summarize_step()
        self.write_step = self.get_write_step()

    async def pipeline(self):
        try:
            await self.direction_step.execute()
            await self.keywords_step.execute()
            await self.search_step.execute()
            await self.summarize_step.execute()
            await self.write_step.execute()
        except Exception:
            raise
