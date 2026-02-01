from fastapi import HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.model import get_models_by_user_id
from app.crud.model_output import count_model_outputs_by_model_id
from app.models import Model
from app.schemas.model import ModelCard
from app.schemas.user import UserCookie
from app.utils.datetime import format_added_at


async def get_models_cards(
    user_cookie: UserCookie,
    session: AsyncSession,
) -> list[ModelCard]:
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
