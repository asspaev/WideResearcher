from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.celery import celery_app
from app.core.redis_cache import get_redis_cache
from app.core.sql import get_session
from app.core.templates import templates
from app.crud.research import create_research
from app.models.research import Research
from app.schemas.user import UserCookie
from app.services.data_fetch import get_research_settings, research_settings_redis_key
from app.utils.dependencies import get_user_cookie

router = APIRouter(prefix=get_settings().prefix.researches, tags=["researches"])

RESEARCH_SETTINGS_TTL = 86400  # 24 часа
_MAX_RESEARCH_NAME_LEN = 120


@router.post("", name="api_create_research")
async def post_create_research(
    request: Request,
    prompt: str = Form(...),
    count_epoch: int = Form(5),
    model_answer: int | None = Form(None),
    model_search: int | None = Form(None),
    model_direction: int | None = Form(None),
    model_parent: str = Form("none"),
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Создание исследования и запуск Celery-задачи"""
    if not model_answer or not model_search:
        settings = await get_research_settings(user_cookie.user_id, session, get_redis_cache())
        model_answer = model_answer or settings.get("model_answer")
        model_search = model_search or settings.get("model_search")

    if not model_answer or not model_search:
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": "Добавьте хотя бы одну модель перед запуском исследования",
                "type": "wrong",
            },
        )

    research_name = prompt[:_MAX_RESEARCH_NAME_LEN]
    research_parent_id = int(model_parent) if model_parent and model_parent != "none" else None

    research: Research = await create_research(
        session,
        user_id=user_cookie.user_id,
        research_name=research_name,
        research_version_name="v1",
        settings_epochs_count=count_epoch,
        model_id_answer=model_answer,
        model_id_search=model_search,
        model_id_direction=model_direction,
        research_parent_id=research_parent_id,
    )
    logger.info(f"Research created: {research.research_id} for user {user_cookie.user_id} {user_cookie.user_login}")

    celery_app.send_task("research.run", args=[research.research_id])
    logger.info(f"Celery task sent: research.run({research.research_id})")

    response = Response(status_code=204)
    response.headers["HX-Redirect"] = f"/researches/{research.research_id}"
    return response


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
    await cache.set(research_settings_redis_key(user_cookie.user_id), settings, ttl=RESEARCH_SETTINGS_TTL)

    if previous_screen == "edit_new_research":
        return templates.TemplateResponse(
            "includes/popups/new_research.html",
            {
                "request": request,
                "page": "edit_new_research",
                "has_settings": True,
                **settings,
            },
        )

    return templates.TemplateResponse(
        "includes/hidden_popup_overlay.html",
        {
            "request": request,
            "has_settings": True,
            "previous_screen": previous_screen,
        },
    )
