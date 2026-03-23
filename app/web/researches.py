from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sql import get_session
from app.core.templates import templates
from app.crud.research import get_research_by_id_and_user_id
from app.schemas.user import UserCookie
from app.services.data_fetch import get_researches_cards
from app.utils.dependencies import get_user_cookie

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

    return templates.TemplateResponse(
        "pages/research.html",
        {
            "request": request,
            "user_cookie": user_cookie,
            "page": "research",
            "research": research,
        },
    )
