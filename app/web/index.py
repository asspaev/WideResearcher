from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sql import get_session
from app.core.templates import templates
from app.crud.research import get_all_researches_with_schedules_by_user_id, get_next_planned_research_by_user_id
from app.models import Research, ResearchSchedule
from app.schemas.research import NearestResearch, ResearchCard
from app.schemas.user import UserCookie
from app.utils.datetime import human_delta
from app.utils.dependencies import get_user_cookie

router = APIRouter()


@router.get("/", name="index")
async def get_index(
    request: Request,
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """Рендер главной страницы"""
    # Получение всех исследования и планов исследований пользователя
    try:
        researches_with_schedules: tuple[Research, ResearchSchedule | None] = (
            await get_all_researches_with_schedules_by_user_id(session, user_cookie.user_id)
        )
    except Exception as e:
        logger.error(f"Error getting researches: {e}")
        raise HTTPException(status_code=500, detail="Error getting researches")

    # Подготовка списка исследований researches
    researches: list[dict] = []
    for research, schedule in researches_with_schedules:
        research_last_update_time: str = human_delta(research.meta_updated_at, datetime.now(timezone.utc))
        if schedule is None:
            schedule_next_launch_time: str = "не запланировано"
        else:
            schedule_next_launch_time: str = human_delta(schedule.scheduled_at, datetime.now(timezone.utc))
        research_card: ResearchCard = ResearchCard(
            research_id=research.research_id,
            research_name=research.research_name,
            research_version_name=research.research_version_name,
            research_last_update_time=research_last_update_time,
            schedule_next_launch_time=schedule_next_launch_time,
        )
        researches.append(research_card)

    # Получение ближайшего исследования пользователя
    try:
        nearest_research_with_schedules: tuple[Research | None, ResearchSchedule | None] = (
            await get_next_planned_research_by_user_id(session, user_cookie.user_id)
        )
    except Exception as e:
        logger.error(f"Error getting nearest research: {e}")
        raise HTTPException(status_code=500, detail="Error getting nearest research")

    # Подготовка ближайшего исследования nearest_research
    if nearest_research_with_schedules[0] is None:
        nearest_research: NearestResearch | None = None
    else:
        research, schedule = nearest_research_with_schedules
        nearest_research: NearestResearch | None = NearestResearch(
            research_id=research.research_id,
            research_name=research.research_name,
            schedule_next_launch_time=human_delta(schedule.scheduled_at, datetime.now(timezone.utc)),
        )

    # Рендер главной страницы
    return templates.TemplateResponse(
        "pages/index.html",
        {
            "request": request,
            "user_cookie": user_cookie,
            "researches": researches,
            "nearest_research": nearest_research,
        },
    )
