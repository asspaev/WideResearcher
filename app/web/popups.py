from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.sql import get_session
from app.core.templates import templates
from app.crud.model import get_model_by_id
from app.models import Model

router = APIRouter(prefix=get_settings().prefix.popups, tags=["popups"])


@router.get("/new-research", name="new_research")
async def get_popup_new_research(request: Request):
    """Рендер всплывающего окна для создания исследования"""
    return templates.TemplateResponse(
        "includes/popups/new_research.html",
        {"request": request},
    )


@router.get("/new-model", name="new_model")
async def get_popup_new_model(request: Request):
    """Рендер всплывающего окна для создания модели"""
    return templates.TemplateResponse(
        "includes/popups/new_model.html",
        {"request": request},
    )


@router.get("/hide", name="hide")
async def get_popup_hide(request: Request):
    """Рендер закрытого всплывающего окна"""
    return templates.TemplateResponse(
        "includes/hidden_popup_overlay.html",
        {"request": request},
    )


@router.get("/edit-model/{model_id}", name="edit_model")
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
