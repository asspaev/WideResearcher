from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.exceptions import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.model import get_models_by_user_id
from app.crud.model_output import count_model_outputs_by_model_id
from app.crud.research import get_all_researches_with_schedules_by_user_id
from app.models import Model, Research, ResearchSchedule
from app.schemas.model import ModelCard
from app.schemas.research import ResearchCard
from app.schemas.user import UserCookie
from app.utils.datetime import format_added_at, human_delta


async def get_models_cards(
    user_cookie: UserCookie,
    session: AsyncSession,
) -> list[ModelCard]:
    """Получение списка моделей пользователя"""

    # Получение моделей пользователя
    try:
        models: list[Model] = await get_models_by_user_id(session, user_cookie.user_id)
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        raise HTTPException(status_code=500, detail="Error getting models")

    # Получение количества использований каждой модели
    count_model_outputs: list[int] = []
    for model in models:
        try:
            count_model_outputs.append(await count_model_outputs_by_model_id(session, model.model_id))
        except Exception as e:
            logger.error(f"Error getting model outputs: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting model outputs, in model {model.model_id}")

    # Подготовка списка моделей
    models_cards: list[ModelCard] = []
    for i in range(len(models)):
        model_created_time: str = format_added_at(models[i].meta_created_at)
        models_cards.append(
            ModelCard(
                model_id=models[i].model_id,
                model_name=models[i].model_name,
                model_created_time=model_created_time,
                model_used_count=count_model_outputs[i],
            )
        )

    # Возврат списка моделей
    return models_cards


async def get_researches_cards(
    user_cookie: UserCookie,
    session: AsyncSession,
) -> list[dict]:
    """Получение списка исследований пользователя"""

    # Получение всех исследования и планов исследований пользователя
    try:
        researches_with_schedules: tuple[Research, ResearchSchedule | None] = (
            await get_all_researches_with_schedules_by_user_id(session, user_cookie.user_id)
        )
    except Exception as e:
        logger.error(f"Error getting researches: {e}")
        raise HTTPException(status_code=500, detail="Error getting researches")

    # Подготовка списка исследований researches
    researches: list[dict] = []
    for research, schedule in researches_with_schedules:
        research_last_update_time: str = human_delta(research.meta_updated_at, datetime.now(timezone.utc))
        if schedule is None:
            schedule_next_launch_time: str = "не запланировано"
        else:
            schedule_next_launch_time: str = human_delta(schedule.scheduled_at, datetime.now(timezone.utc))
        research_card: ResearchCard = ResearchCard(
            research_id=research.research_id,
            research_name=research.research_name,
            research_version_name=research.research_version_name,
            research_last_update_time=research_last_update_time,
            schedule_next_launch_time=schedule_next_launch_time,
        )
        researches.append(research_card)

    # Возврат списка исследований
    return researches
