from loguru import logger

from app.crud.research import update_research_stage
from app.models.research import RESEARCH_STAGES, Research
from app.services.prompts import build_rename_messages

from .base import ResearchStepBase


class RenameResearchStep(ResearchStepBase):
    """Генерация короткого названия исследования на основе h1 и исходного запроса."""

    async def execute(self) -> None:
        """Генерирует и сохраняет название исследования через LLM.

        Шаг пропускается, если research_body_finish пуст или отсутствует.
        """
        research: Research = self._research

        if not research.research_body_finish:
            logger.info(f"{self._log_extra()} RenameResearchStep: research_body_finish is empty, skipping")
            return

        await update_research_stage(self._session, research, RESEARCH_STAGES["RENAME"])

        llm = await self._get_llm(research.model_id_answer)
        if llm is None:
            logger.error(
                f"{self._log_extra()} RenameResearchStep: model {research.model_id_answer} not found, skipping"
            )
            return

        segments = research.research_body_finish.get("segments", [])
        h1_content: str | None = None
        if segments and segments[0].get("type") == "h1":
            h1_content = segments[0].get("content", "")
        else:
            logger.warning(f"{self._log_extra()} RenameResearchStep: first segment is not h1, proceeding anyway")
            if segments:
                h1_content = segments[0].get("content", "")

        query: str = (research.research_body_start or {}).get("query", research.research_name)

        if research.research_name != query:
            logger.info(
                f"{self._log_extra()} RenameResearchStep: skipping, user already renamed "
                f"research to '{research.research_name}'"
            )
            return

        messages = build_rename_messages(h1=h1_content or "", query=query)

        try:
            name = await llm.generate(
                messages,
                session=self._session,
                model_id=research.model_id_answer,
                research_id=research.research_id,
                step_type="rename",
            )
            name = (name or "").strip()[:100]
            if name:
                research.research_name = name
                await self._session.commit()
                logger.info(f"{self._log_extra()} RenameResearchStep: renamed to '{name}'")
            else:
                logger.warning(f"{self._log_extra()} RenameResearchStep: LLM returned empty name, keeping original")
        except Exception as exc:
            logger.exception(f"{self._log_extra()} RenameResearchStep: failed: {exc}")
