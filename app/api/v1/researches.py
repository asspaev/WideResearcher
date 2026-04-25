from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.celery import celery_app
from app.core.redis_cache import get_redis_cache
from app.core.sql import get_session
from app.core.templates import templates
from app.crud.research import archive_research, create_research, get_research_by_id, update_research_name
from app.models.research import Research
from app.schemas.user import UserCookie
from app.services.data_fetch import get_research_settings, get_researches_cards, research_settings_redis_key
from app.utils.dependencies import get_user_cookie

router = APIRouter(prefix=get_settings().prefix.researches, tags=["researches"])

RESEARCH_SETTINGS_TTL = 86400  # 24 часа
_MAX_RESEARCH_NAME_LEN = 120


@router.post("", name="api_create_research")
async def post_create_research(
    request: Request,
    prompt: str = Form(...),
    model_answer: int | None = Form(None),
    model_search: int | None = Form(None),
    model_direction: int | None = Form(None),
    model_embed: int | None = Form(None),
    model_reranker: int | None = Form(None),
    model_parent: str = Form("none"),
    n_async_parse: int | None = Form(None),
    scenario_type: str | None = Form(None),
    search_areas: str | None = Form(None),
    exclude_search_areas: str | None = Form(None),
    n_vectors: int | None = Form(None),
    n_search_queries: int | None = Form(None),
    n_top_search_results: int | None = Form(None),
    n_top_bm25_chunks: int | None = Form(None),
    n_top_embed_chunks: int | None = Form(None),
    n_top_rerank_chunks: int | None = Form(None),
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Создание исследования и запуск Celery-задачи"""
    logger.debug(
        "post_create_research params: prompt={!r}, model_answer={}, model_search={}, "
        "model_direction={}, model_embed={}, model_reranker={}, model_parent={!r}, "
        "n_async_parse={}, scenario_type={!r}, search_areas={!r}, exclude_search_areas={!r}, "
        "n_vectors={}, n_search_queries={}, n_top_search_results={}, "
        "n_top_bm25_chunks={}, n_top_embed_chunks={}, n_top_rerank_chunks={}",
        prompt,
        model_answer,
        model_search,
        model_direction,
        model_embed,
        model_reranker,
        model_parent,
        n_async_parse,
        scenario_type,
        search_areas,
        exclude_search_areas,
        n_vectors,
        n_search_queries,
        n_top_search_results,
        n_top_bm25_chunks,
        n_top_embed_chunks,
        n_top_rerank_chunks,
    )
    if not model_answer or not model_search or model_direction is None or model_embed is None or model_reranker is None:
        settings = await get_research_settings(user_cookie.user_id, session, get_redis_cache())
        model_answer = model_answer or settings.get("model_answer")
        model_search = model_search or settings.get("model_search")
        if model_direction is None:
            model_direction = settings.get("model_direction")
        if model_embed is None:
            model_embed = settings.get("model_embed")
        if model_reranker is None:
            model_reranker = settings.get("model_reranker")
        logger.debug(f"Model direction for new research: {model_direction}")

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
        model_id_answer=model_answer,
        model_id_search=model_search,
        model_id_direction=model_direction,
        model_id_embed=model_embed,
        model_id_reranker=model_reranker,
        research_parent_id=research_parent_id,
        research_body_start={"prompt": research_name},
        settings_n_async_parse=n_async_parse,
        settings_scenario_type=scenario_type,
        settings_search_areas=search_areas or None,
        settings_exclude_search_areas=exclude_search_areas or None,
        settings_n_vectors=n_vectors,
        settings_n_search_queries=n_search_queries,
        settings_n_top_search_results=n_top_search_results,
        settings_n_top_bm25_chunks=n_top_bm25_chunks,
        settings_n_top_embed_chunks=n_top_embed_chunks,
        settings_n_top_rerank_chunks=n_top_rerank_chunks,
    )
    logger.info(f"Research created: {research.research_id} for user {user_cookie.user_id} {user_cookie.user_login}")

    celery_app.send_task("research.run", args=[research.research_id])
    logger.info(f"Celery task sent: research.run({research.research_id})")

    response = Response(status_code=204)
    response.headers["HX-Redirect"] = f"/researches/{research.research_id}"
    return response


@router.put("/{research_id}", name="api_update_research")
async def put_update_research(
    request: Request,
    research_id: int,
    research_name: str = Form(...),
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Обновление названия исследования"""
    research = await get_research_by_id(session, research_id)
    old_name: str = research.research_name

    await update_research_name(session, research_id, research_name)
    logger.info(f"Research renamed: {research_id} for user {user_cookie.user_id} {user_cookie.user_login}")

    researches = await get_researches_cards(user_cookie, session)

    return templates.TemplateResponse(
        "includes/popups/research_edited.html",
        {
            "request": request,
            "researches": researches,
            "old_name": old_name,
            "new_name": research_name,
            "research_id": research_id,
        },
    )


@router.delete("/{research_id}", name="api_delete_research")
async def delete_research(
    request: Request,
    research_id: int,
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Архивирование исследования"""

    # TODO Проверить, что исследование принадлежит пользователю

    research = await get_research_by_id(session, research_id)
    research_name: str = research.research_name

    await archive_research(session, research_id)
    logger.info(f"Research archived: {research_id} for user {user_cookie.user_id} {user_cookie.user_login}")

    researches = await get_researches_cards(user_cookie, session)

    return templates.TemplateResponse(
        "includes/popups/research_deleted.html",
        {
            "request": request,
            "researches": researches,
            "research_name": research_name,
        },
    )


@router.post("/settings", name="api_edit_new_research")
async def api_edit_new_research(
    request: Request,
    model_answer: int | None = Form(None),
    model_search: int | None = Form(None),
    model_direction: int | None = Form(None),
    model_embed: int | None = Form(None),
    model_reranker: int | None = Form(None),
    model_parent: str = Form("none"),
    n_async_parse: int = Form(3),
    scenario_type: str = Form("NORMAL"),
    search_areas: str = Form(""),
    exclude_search_areas: str = Form(""),
    n_vectors: int = Form(5),
    n_search_queries: int = Form(5),
    n_top_search_results: int = Form(10),
    n_top_bm25_chunks: int = Form(50),
    n_top_embed_chunks: int = Form(30),
    n_top_rerank_chunks: int = Form(15),
    previous_screen: str | None = Form(None),
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Сохранение настроек нового исследования в Redis"""
    settings = {
        "model_answer": model_answer,
        "model_search": model_search,
        "model_direction": model_direction,
        "model_embed": model_embed,
        "model_reranker": model_reranker,
        "model_parent": model_parent,
        "n_async_parse": n_async_parse,
        "scenario_type": scenario_type,
        "search_areas": search_areas or None,
        "exclude_search_areas": exclude_search_areas or None,
        "n_vectors": n_vectors,
        "n_search_queries": n_search_queries,
        "n_top_search_results": n_top_search_results,
        "n_top_bm25_chunks": n_top_bm25_chunks,
        "n_top_embed_chunks": n_top_embed_chunks,
        "n_top_rerank_chunks": n_top_rerank_chunks,
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
