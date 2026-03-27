import asyncio

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery import celery_app
from app.core.sql import get_sql
from app.crud.model import get_model_by_id
from app.crud.model_output import create_model_output
from app.crud.research import get_research_by_id
from app.crud.research_epoch import create_research_epoch
from app.models.model_output import ModelResponseStatus
from app.models.research import Research
from app.services.llm_client import LLMClient
from app.services.prompts import build_direction_messages


@celery_app.task(name="research.run")
def run_research(research_id: int) -> None:
    asyncio.run(_run_research(research_id))


async def _run_research(research_id: int) -> None:
    db = get_sql()
    async with db.session_factory() as session:
        research = await get_research_by_id(session, research_id)
        if research is None:
            logger.error(f"run_research: research {research_id} not found")
            return

        await _step_direction_brainstorm(session, research)


async def _step_direction_brainstorm(session: AsyncSession, research: Research) -> str:
    """Шаг 1: определение направления исследования.

    Выполняет один вызов model_id_direction и сохраняет результат
    в model_outputs (epoch_id=0, step_type="direction_brainstorm").

    Args:
        session: Активная сессия БД.
        research: ORM-объект исследования.

    Returns:
        Ответ модели или пустую строку при ошибке.
    """
    if research.model_id_direction is None:
        logger.warning(
            f"_step_direction_brainstorm: research {research.research_id} has no model_id_direction, skipping"
        )
        return ""

    model = await get_model_by_id(session, research.model_id_direction)
    if model is None:
        logger.error(f"_step_direction_brainstorm: direction model {research.model_id_direction} not found")
        return ""

    llm = LLMClient(
        model_name=model.model_api_model,
        base_url=model.model_base_url,
        api_key=model.model_key_api,
    )

    messages = build_direction_messages(query=research.research_name)

    status = ModelResponseStatus.COMPLETE
    output_payload: dict = {}
    direction_content: str | None = None

    try:
        result = await llm.generate(messages)
        output_payload = {"content": result}
        direction_content = result
        logger.info(f"_step_direction_brainstorm: done (research_id={research.research_id})")
    except Exception as exc:
        status = ModelResponseStatus.ERROR
        output_payload = {"error": str(exc)}
        logger.error(f"_step_direction_brainstorm: failed (research_id={research.research_id}): {exc}")

    await create_model_output(
        session=session,
        model_id=research.model_id_direction,
        research_id=research.research_id,
        epoch_id=0,
        step_type="direction_brainstorm",
        model_input={"messages": messages},
        model_output=output_payload,
        response_status=status,
    )

    await create_research_epoch(
        session=session,
        research_id=research.research_id,
        epoch_id=0,
        body_start={"query": research.research_name},
        body_finish={},
        direction_content=direction_content,
    )

    return direction_content or ""
