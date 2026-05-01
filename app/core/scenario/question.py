from sqlalchemy.ext.asyncio import AsyncSession

from app.core.research import (
    BM25ScoringStep,
    ChunkingResearchStep,
    DirectionResearchStep,
    EmbedScoringStep,
    KeywordsResearchStep,
    RenameResearchStep,
    RerankScoringStep,
    SearchResearchStep,
    SummarizeResearchStep,
)
from app.models.research import Research

from .base import ScenarioBase


class QuestionScenario(ScenarioBase):

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
        self.chunking_step = ChunkingResearchStep(session, research)
        self.bm25_scoring_step = BM25ScoringStep(session, research)
        self.embed_scoring_step = EmbedScoringStep(session, research)
        self.rerank_scoring_step = RerankScoringStep(session, research)
        self.summarize_step = SummarizeResearchStep(session, research)
        self.write_step = self.get_write_step()
        self.rename_step = RenameResearchStep(session, research)

    async def pipeline(self):
        try:
            if not self._should_skip_stage("DIRECTION"):
                await self.direction_step.execute()
            if not self._should_skip_stage("KEYWORDS"):
                await self.keywords_step.execute()
            if not self._should_skip_stage("SEARCH"):
                await self.search_step.execute()
            if not self._should_skip_stage("SCRAPE"):
                await self.chunking_step.execute()
            if not self._should_skip_stage("SCORING_BM25"):
                await self.bm25_scoring_step.execute()
            if not self._should_skip_stage("SCORING_EMBED"):
                await self.embed_scoring_step.execute()
            if not self._should_skip_stage("SCORING_RERANK"):
                await self.rerank_scoring_step.execute()
            if not self._should_skip_stage("SUMMARIZE"):
                await self.summarize_step.execute()
            if not self._should_skip_stage("WRITE"):
                await self.write_step.execute()
            if not self._should_skip_stage("RENAME"):
                await self.rename_step.execute()
        except Exception:
            raise
