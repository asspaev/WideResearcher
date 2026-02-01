from fastapi import APIRouter, Depends, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sql import get_session
from app.core.templates import templates
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
