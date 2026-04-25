from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.exceptions import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_cache import RedisCache
from app.crud.model import get_model_by_id, get_models_by_user_id
from app.crud.model_output import count_model_outputs_by_model_id
from app.crud.research import (
    get_all_researches_with_schedules_by_user_id,
    get_planned_schedule_by_research_id,
    get_research_by_id,
)
from app.models import Model, Research, ResearchSchedule
from app.schemas.model import ModelCard
from app.schemas.research import ResearchCard
from app.schemas.user import UserCookie
from app.utils.datetime import format_added_at, format_interval, human_delta


def research_settings_redis_key(user_id: int) -> str:
    return f"research_settings:{user_id}"


async def get_research_settings(
    user_id: int,
    session: AsyncSession,
    cache: RedisCache,
) -> dict:
    """Возвращает настройки нового исследования из Redis или дефолтные значения.

    Дефолт: model_answer/model_search = первая модель пользователя (или None).
    """
    saved = await cache.get(research_settings_redis_key(user_id))
    if saved:
        return saved

    models: list[Model] = await get_models_by_user_id(session, user_id)
    generative = [m for m in models if m.model_type == "generative"]
    embedding = [m for m in models if m.model_type == "embedding"]
    default_generative_id: int | None = generative[0].model_id if generative else None
    default_embedding_id: int | None = embedding[0].model_id if embedding else None
    return {
        "model_answer": default_generative_id,
        "model_search": default_generative_id,
        "model_direction": default_generative_id,
        "model_embed": default_embedding_id,
        "model_reranker": default_generative_id,
        "model_parent": "none",
        "n_async_parse": 3,
        "scenario_type": "NORMAL",
        "search_areas": None,
        "exclude_search_areas": None,
        "n_vectors": 5,
        "n_search_queries": 5,
        "n_top_search_results": 10,
        "n_top_bm25_chunks": 50,
        "n_top_embed_chunks": 30,
        "n_top_rerank_chunks": 15,
    }


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
        if models[i].model_type == "generative":
            model_type = "Генеративная"
        elif models[i].model_type == "embedding":
            model_type = "Эмбединг"
        else:
            model_type = "Неизвестный тип"
        models_cards.append(
            ModelCard(
                model_id=models[i].model_id,
                model_name=models[i].model_name,
                model_type=model_type,
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
            research_stage=research.research_stage,
            research_version_name=research.research_version_name,
            research_last_update_time=research_last_update_time,
            schedule_next_launch_time=schedule_next_launch_time,
        )
        researches.append(research_card)

    # Возврат списка исследований
    return researches


async def get_research_detail(
    research: Research,
    session: AsyncSession,
) -> dict:
    """Собирает детальные данные об исследовании для страницы research.

    Args:
        research: ORM-объект исследования.
        session: Активная сессия БД.

    Returns:
        Словарь с полями: segments, schedule_next_launch_time, schedule_interval,
        research_last_update_time, model_answer_name, model_search_name,
        model_direction_name, parent_version_name, search_areas_text, has_schedule.
    """
    now = datetime.now(timezone.utc)

    # Расписание
    schedule = await get_planned_schedule_by_research_id(session, research.research_id)
    if schedule is not None:
        schedule_next_launch_time = human_delta(schedule.scheduled_at, now)
        schedule_interval = format_interval(schedule.repeat_interval)
    else:
        schedule_next_launch_time = "не запланировано"
        schedule_interval = None

    # Время последнего обновления
    research_last_update_time = human_delta(research.meta_updated_at, now)

    # Модели
    model_answer = await get_model_by_id(session, research.model_id_answer)
    model_search = await get_model_by_id(session, research.model_id_search)
    model_direction = (
        await get_model_by_id(session, research.model_id_direction) if research.model_id_direction else None
    )

    # Родительское исследование
    parent = await get_research_by_id(session, research.research_parent_id) if research.research_parent_id else None

    # Сегменты результата исследования
    segments: list[dict] | None = None
    if research.research_body_finish:
        body = research.research_body_finish
        if isinstance(body, list):
            segments = body
        elif isinstance(body, dict):
            segments = body.get("segments")

    # Зоны поиска
    search_areas_text = research.settings_search_areas or None

    return {
        "segments": segments,
        "has_schedule": schedule is not None,
        "schedule_next_launch_time": schedule_next_launch_time,
        "schedule_interval": schedule_interval,
        "research_last_update_time": research_last_update_time,
        "model_answer_name": model_answer.model_name if model_answer else None,
        "model_search_name": model_search.model_name if model_search else None,
        "model_direction_name": model_direction.model_name if model_direction else None,
        "parent_version_name": parent.research_version_name if parent else None,
        "search_areas_text": search_areas_text,
    }
