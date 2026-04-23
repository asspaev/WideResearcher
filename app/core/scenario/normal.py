from sqlalchemy.ext.asyncio import AsyncSession

from app.core.research import (
    BM25ScoringStep,
    DirectionResearchStep,
    EmbedScoringStep,
    KeywordsResearchStep,
    RerankScoringStep,
    SearchResearchStep,
)
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
        self.bm25_scoring_step = BM25ScoringStep(session, research)
        self.embed_scoring_step = EmbedScoringStep(session, research)
        self.rerank_scoring_step = RerankScoringStep(session, research)
        # self.write_step = self.get_write_step()

    async def pipeline(self):
        try:
            await self.direction_step.execute()
            await self.keywords_step.execute()
            await self.search_step.execute()
            await self.bm25_scoring_step.execute()
            await self.embed_scoring_step.execute()
            await self.rerank_scoring_step.execute()
            # await self.write_step.execute()
        except Exception:
            raise
