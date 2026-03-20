from fastapi import APIRouter, Depends, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.redis_cache import get_redis_cache
from app.core.sql import get_session
from app.core.templates import templates
from app.crud.model import get_model_by_id, get_models_by_user_id
from app.models import Model
from app.schemas.user import UserCookie
from app.utils.dependencies import get_user_cookie

router = APIRouter(prefix=get_settings().prefix.popups, tags=["popups"])


@router.get("/hide", name="hide")
async def get_popup_hide(request: Request):
    """Рендер закрытого всплывающего окна"""
    return templates.TemplateResponse(
        "includes/hidden_popup_overlay.html",
        {"request": request},
    )


@router.get("/researches/new", name="new_research")
async def get_popup_new_research(
    request: Request,
    user_cookie: UserCookie = Depends(get_user_cookie),
):
    """Рендер всплывающего окна для создания исследования"""
    cache = get_redis_cache()
    saved: dict | None = await cache.get(f"research_settings:{user_cookie.user_id}")

    return templates.TemplateResponse(
        "includes/popups/new_research.html",
        {
            "request": request,
            "page": "edit_new_research",
            **(saved or {}),
        },
    )


@router.get("/researches/new/settings", name="edit_new_research")
async def get_popup_edit_new_research(
    request: Request,
    previous_screen: str | None = None,
    reset: bool = False,
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Рендер всплывающего окна редактирования нового исследования"""
    models: list[Model] = await get_models_by_user_id(session, user_cookie.user_id)

    saved: dict = {}
    if not reset:
        cache = get_redis_cache()
        saved = await cache.get(f"research_settings:{user_cookie.user_id}") or {}

    return templates.TemplateResponse(
        "includes/popups/edit_new_research.html",
        {
            "request": request,
            "models": models,
            "previous_screen": previous_screen,
            **saved,
        },
    )


@router.get("/models/new", name="new_model")
async def get_popup_new_model(request: Request):
    """Рендер всплывающего окна для создания модели"""
    return templates.TemplateResponse(
        "includes/popups/new_model.html",
        {"request": request},
    )


@router.get("/models/{model_id}/edit", name="edit_model")
async def get_edit_model(
    request: Request,
    model_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Рендер всплывающего окна редактирования модели"""
    # TODO Проверка, что модель принадлежит пользователю

    # Поиск модели
    model: Model | None = await get_model_by_id(session, model_id)

    # TODO Обработка при не удачном поиске

    # Рендер всплывающего онка
    return templates.TemplateResponse(
        "includes/popups/edit_model.html",
        {
            "request": request,
            "model": model,
        },
    )


@router.get("/models/{model_id}/delete", name="delete_model")
async def get_delete_model(
    request: Request,
    model_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Рендер всплывающего окна удаления модели"""
    # TODO Проверка, что модель принадлежит пользователю

    # Поиск модели
    model: Model | None = await get_model_by_id(session, model_id)
    model_name: str = model.model_name

    # TODO Обработка при не удачном поиске

    # Рендер всплывающего онка
    return templates.TemplateResponse(
        "includes/popups/delete_model.html",
        {
            "request": request,
            "model": model,
            "model_name": model_name,
        },
    )
