import asyncio

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery import celery_app
from app.core.sql import get_sql
from app.crud.model import get_model_by_id
from app.crud.model_output import create_model_output
from app.crud.research import get_research_by_id
from app.models.model_output import ModelResponseStatus
from app.models.research import Research
from app.services.llm_client import LLMClient
from app.services.prompts import build_direction_messages

DIRECTION_ITERATIONS = 5


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
    """Шаг 1: итеративный брейншторм направления исследования.

    Вызывает model_id_direction DIRECTION_ITERATIONS раз, каждый раз расширяя
    накопленный контекст ответами предыдущих итераций. Все вызовы сохраняются
    в model_outputs (epoch_id=0, step_type="direction_brainstorm").

    Args:
        session: Активная сессия БД.
        research: ORM-объект исследования.

    Returns:
        Накопленный контекст всех успешных итераций.
    """
    if research.model_id_direction is None:
        logger.warning(
            f"_step_direction_brainstorm: research {research.research_id} " "has no model_id_direction, skipping"
        )
        return ""

    model = await get_model_by_id(session, research.model_id_direction)
    if model is None:
        logger.error(f"_step_direction_brainstorm: direction model " f"{research.model_id_direction} not found")
        return ""

    llm = LLMClient(
        model_name=model.model_api_model,
        base_url=model.model_base_url,
        api_key=model.model_key_api,
    )

    accumulated_context = ""

    for i in range(DIRECTION_ITERATIONS):
        messages = build_direction_messages(
            query=research.research_name,
            accumulated_context=accumulated_context,
        )

        status = ModelResponseStatus.COMPLETE
        output_payload: dict = {}

        try:
            result = await llm.generate(messages)
            output_payload = {"content": result}
            accumulated_context += f"\n### Итерация {i + 1}\n{result}"
            logger.info(
                f"_step_direction_brainstorm: iteration {i + 1}/{DIRECTION_ITERATIONS} done "
                f"(research_id={research.research_id})"
            )
        except Exception as exc:
            status = ModelResponseStatus.ERROR
            output_payload = {"error": str(exc)}
            logger.error(
                f"_step_direction_brainstorm: iteration {i + 1}/{DIRECTION_ITERATIONS} failed "
                f"(research_id={research.research_id}): {exc}"
            )

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

    return accumulated_context
