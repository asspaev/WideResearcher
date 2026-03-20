from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.redis_cache import get_redis_cache
from app.core.sql import get_session
from app.core.templates import templates
from app.crud.model import get_models_by_user_id
from app.models import Model
from app.schemas.user import UserCookie
from app.utils.dependencies import get_user_cookie

router = APIRouter(prefix=get_settings().prefix.researches, tags=["researches"])

RESEARCH_SETTINGS_TTL = 86400  # 24 часа


def _settings_redis_key(user_id: int) -> str:
    return f"research_settings:{user_id}"


@router.post("/settings", name="api_edit_new_research")
async def api_edit_new_research(
    request: Request,
    count_epoch: int = Form(5),
    model_answer: int | None = Form(None),
    model_search: int | None = Form(None),
    model_direction: int | None = Form(None),
    model_parent: str = Form("none"),
    previous_screen: str | None = Form(None),
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Сохранение настроек нового исследования в Redis"""
    settings = {
        "count_epoch": count_epoch,
        "model_answer": model_answer,
        "model_search": model_search,
        "model_direction": model_direction,
        "model_parent": model_parent,
    }
    cache = get_redis_cache()
    await cache.set(_settings_redis_key(user_cookie.user_id), settings, ttl=RESEARCH_SETTINGS_TTL)

    if previous_screen == "edit_new_research":
        return templates.TemplateResponse(
            "includes/popups/new_research.html",
            {
                "request": request,
                "page": "edit_new_research",
                **settings,
            },
        )

    return templates.TemplateResponse(
        "includes/hidden_popup_overlay.html",
        {"request": request},
    )
