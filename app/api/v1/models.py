from fastapi import APIRouter, Depends, Form, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.sql import get_session
from app.core.templates import templates
from app.crud.model import create_model, model_exists_by_user_and_name, update_model
from app.models import Model
from app.schemas.model import ModelCard
from app.schemas.user import UserCookie
from app.services.data_fetch import get_models_cards
from app.utils.dependencies import get_user_cookie
from app.utils.validates import validate_correct_model_name

router = APIRouter(prefix=get_settings().prefix.models, tags=["models"])


@router.post("", name="api_create_model")
async def post_create_model(
    request: Request,
    model_name: str = Form(...),
    model_type: str = Form(...),
    model_api_type: str | None = Form(None),
    model_api_key: str | None = Form(None),
    model_path: str | None = Form(None),
    model_key_answer: str | None = Form(None),
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Создание модели"""

    # Проверить, что название модели от 3 до 120 символов
    correct_model_name: str | None = validate_correct_model_name(model_name)
    if correct_model_name:
        logger.error(f"Model name is not valid: {model_name}")
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": correct_model_name,
                "type": "wrong",
            },
        )

    # Проверить, что модели с таким названием не существует
    if await model_exists_by_user_and_name(session, user_cookie.user_id, model_name):
        logger.error(f"Model already exists: {model_name} for user {user_cookie.user_id} {user_cookie.user_login}")
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": "Модель с таким именем уже существует",
                "type": "wrong",
            },
        )

    # Проверить, что необходимые поля заполнены
    if model_type == "api":
        if not model_api_type:
            logger.error(f"Model api type is not valid: {model_api_type}")
            return templates.TemplateResponse(
                "partials/result_form.html",
                {
                    "request": request,
                    "message": "Тип API не указан",
                    "type": "wrong",
                },
            )
        elif not model_api_key:
            logger.error(f"Model api key is not valid: {model_api_key}")
            return templates.TemplateResponse(
                "partials/result_form.html",
                {
                    "request": request,
                    "message": "Ключ API не указан",
                    "type": "wrong",
                },
            )
    if model_type == "vllm":
        if not model_path:
            logger.error(f"Model path is not valid: {model_path}")
            return templates.TemplateResponse(
                "partials/result_form.html",
                {
                    "request": request,
                    "message": "Путь до модели не указан",
                    "type": "wrong",
                },
            )
        elif not model_key_answer:
            logger.error(f"Model key answer is not valid: {model_key_answer}")
            return templates.TemplateResponse(
                "partials/result_form.html",
                {
                    "request": request,
                    "message": "Ключ ответа не указан",
                    "type": "wrong",
                },
            )

    # Сохранить модель в базу данных
    model: Model = await create_model(
        session,
        user_cookie.user_id,
        model_type,
        model_name,
        model_api_type,
        model_path,
        model_api_key,
        model_key_answer,
    )
    logger.info(f"Model created: {model.model_id} for user {user_cookie.user_id} {user_cookie.user_login}")

    # Получение всех моделей пользователя
    models_cards: list[ModelCard] = await get_models_cards(user_cookie, session)

    # Вернуть результат
    return templates.TemplateResponse(
        "includes/popups/model_created.html",
        {
            "request": request,
            "model_name": model_name,
            "models": models_cards,
        },
    )


@router.put("/{model_id}", name="api_update_model")
async def put_update_model(
    request: Request,
    model_id: int,
    model_name: str = Form(...),
    model_type: str | None = Form(None),
    model_api_type: str | None = Form(None),
    model_api_key: str | None = Form(None),
    model_path: str | None = Form(None),
    model_key_answer: str | None = Form(None),
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Обновление модели"""
    logger.debug(
        f"Received data: {model_id}, {model_name}, {model_type}, {model_api_type}, {model_api_key}, {model_path}, {model_key_answer}"
    )

    # Проверить, что необходимые поля заполнены
    if model_type == "api":
        if not model_api_type:
            logger.error(f"Model api type is not valid: {model_api_type}")
            return templates.TemplateResponse(
                "partials/result_form.html",
                {
                    "request": request,
                    "message": "Тип API не указан",
                    "type": "wrong",
                },
            )
        elif not model_api_key:
            logger.error(f"Model api key is not valid: {model_api_key}")
            return templates.TemplateResponse(
                "partials/result_form.html",
                {
                    "request": request,
                    "message": "Ключ API не указан",
                    "type": "wrong",
                },
            )
    if model_type == "vllm":
        if not model_path:
            logger.error(f"Model path is not valid: {model_path}")
            return templates.TemplateResponse(
                "partials/result_form.html",
                {
                    "request": request,
                    "message": "Путь до модели не указан",
                    "type": "wrong",
                },
            )
        elif not model_key_answer:
            logger.error(f"Model key answer is not valid: {model_key_answer}")
            return templates.TemplateResponse(
                "partials/result_form.html",
                {
                    "request": request,
                    "message": "Ключ ответа не указан",
                    "type": "wrong",
                },
            )

    # Обновление записи в базе данных
    model: Model = await update_model(
        session,
        model_id,
        model_type=model_type,
        model_name=model_name,
        model_api_type=model_api_type,
        model_path=model_path,
        model_key_api=model_api_key,
        model_key_answer=model_key_answer,
    )
    logger.info(f"Model updated: {model.model_id} for user {user_cookie.user_id} {user_cookie.user_login}")

    # Получение всех моделей пользователя
    models_cards: list[ModelCard] = await get_models_cards(user_cookie, session)

    # Вернуть результат
    return templates.TemplateResponse(
        "includes/popups/model_edited.html",
        {
            "request": request,
            "model_name": model_name,
            "models": models_cards,
        },
    )
