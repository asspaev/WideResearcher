from fastapi import APIRouter, Depends, Form, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.sql import get_session
from app.core.templates import templates
from app.crud.model import create_model, delete_model, get_model_by_id, model_exists_by_user_and_name, update_model
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
    model_base_url: str = Form(...),
    model_api_model: str = Form(...),
    model_api_key: str | None = Form(None),
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Создание модели"""

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

    model: Model = await create_model(
        session,
        user_cookie.user_id,
        model_name,
        model_type,
        model_base_url,
        model_api_model,
        model_api_key,
    )
    logger.info(f"Model created: {model.model_id} for user {user_cookie.user_id} {user_cookie.user_login}")

    models_cards: list[ModelCard] = await get_models_cards(user_cookie, session)

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
    model_base_url: str = Form(...),
    model_api_model: str = Form(...),
    model_api_key: str | None = Form(None),
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Обновление модели"""

    # TODO Проверить, что модель принадлежит пользователю

    model: Model = await update_model(
        session,
        model_id,
        model_name=model_name,
        model_key_api=model_api_key,
        model_base_url=model_base_url,
        model_api_model=model_api_model,
    )
    logger.info(f"Model updated: {model.model_id} for user {user_cookie.user_id} {user_cookie.user_login}")

    models_cards: list[ModelCard] = await get_models_cards(user_cookie, session)

    return templates.TemplateResponse(
        "includes/popups/model_edited.html",
        {
            "request": request,
            "model_name": model_name,
            "models": models_cards,
        },
    )


@router.delete("/{model_id}", name="api_delete_model")
async def put_update_model(
    request: Request,
    model_id: int,
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Удаление модели"""

    # TODO Проверить, что модель принадлежит пользователю

    model: Model = await get_model_by_id(session, model_id)
    model_name: str = model.model_name

    await delete_model(session, model_id)
    logger.info(f"Model deleted: {model_id} for user {user_cookie.user_id} {user_cookie.user_login}")

    models_cards: list[ModelCard] = await get_models_cards(user_cookie, session)

    return templates.TemplateResponse(
        "includes/popups/model_deleted.html",
        {
            "request": request,
            "models": models_cards,
            "model_name": model_name,
        },
    )
