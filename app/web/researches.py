import asyncio

from fastapi import APIRouter, Depends, Request, WebSocket
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.research_stages import STAGE_LABELS_ACTIVE, STAGE_LABELS_DONE, STAGE_ORDER
from app.core.research_timers import compute_ws_timers, get_stage_timers
from app.core.sql import get_session
from app.core.templates import templates
from app.crud.research import get_research_by_id, get_research_by_id_and_user_id
from app.models.research import ResearchStatus
from app.schemas.user import UserCookie
from app.services.data_fetch import get_research_detail, get_researches_cards
from app.utils.dependencies import get_user_cookie
from app.utils.secrets import decode_jwt

router = APIRouter()


@router.get("/researches", name="researches")
async def get_researches(
    request: Request,
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Рендер страницы со списком исследований"""
    # Получение исследований пользователя
    researches: list[dict] = await get_researches_cards(user_cookie, session)

    # Рендер
    return templates.TemplateResponse(
        "pages/researches.html",
        {
            "request": request,
            "user_cookie": user_cookie,
            "page": "researches",
            "researches": researches,
        },
    )


@router.websocket("/ws/researches/{research_id}")
async def ws_research_status(
    websocket: WebSocket,
    research_id: int,
    session: AsyncSession = Depends(get_session),
):
    """WebSocket для отслеживания этапов исследования в реальном времени."""
    token = websocket.cookies.get("access_token")
    settings = get_settings()
    try:
        data = decode_jwt(token)
        user_id = data["user_id"]
    except Exception:
        await websocket.close(code=4401)
        return

    research = await get_research_by_id_and_user_id(session, research_id, user_id)
    if research is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    try:
        stage_ts = await get_stage_timers(research_id)
        timers, active_elapsed = compute_ws_timers(stage_ts, research.research_stage)
        await websocket.send_json(
            {
                "stage": research.research_stage,
                "status": research.research_status.value,
                "error": research.research_error_body,
                "timers": timers,
                "active_elapsed": active_elapsed,
            }
        )

        if research.research_status in (ResearchStatus.COMPLETE, ResearchStatus.ERROR):
            return

        last_stage = research.research_stage
        while True:
            await asyncio.sleep(settings.app.ws_research_check_status)
            await session.refresh(research)

            stage_changed = research.research_stage != last_stage
            finished = research.research_status != ResearchStatus.IN_PROCESS

            if stage_changed or finished:
                last_stage = research.research_stage
                stage_ts = await get_stage_timers(research_id)
                timers, active_elapsed = compute_ws_timers(stage_ts, research.research_stage)
                await websocket.send_json(
                    {
                        "stage": research.research_stage,
                        "status": research.research_status.value,
                        "error": research.research_error_body,
                        "timers": timers,
                        "active_elapsed": active_elapsed,
                    }
                )
                if finished:
                    break
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/researches/{research_id}", name="research")
async def get_research(
    request: Request,
    research_id: int,
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    research = await get_research_by_id_and_user_id(session, research_id, user_cookie.user_id)

    if research is None:
        return RedirectResponse(url="/researches", status_code=302)

    detail = await get_research_detail(research, session)

    return templates.TemplateResponse(
        "pages/research.html",
        {
            "request": request,
            "user_cookie": user_cookie,
            "page": "research",
            "research": research,
            "stage_order": STAGE_ORDER,
            "stage_labels_active": STAGE_LABELS_ACTIVE,
            "stage_labels_done": STAGE_LABELS_DONE,
            **detail,
        },
    )
