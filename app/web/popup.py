from fastapi import APIRouter, Request

from app.config import get_settings
from app.core.templates import templates

router = APIRouter(prefix=get_settings().prefix.popup, tags=["popup"])


@router.get("/new_research", name="new_research")
async def get_popup_new_research(request: Request):
    """Рендер всплывающего окна для создания исследования"""
    return templates.TemplateResponse(
        "includes/popups/new_research.html",
        {"request": request},
    )


@router.get("/hide", name="hide")
async def get_popup_new_research(request: Request):
    """Рендер закрытое всплывающее окно"""
    return templates.TemplateResponse(
        "includes/hidden_popup_overlay.html",
        {"request": request},
    )
