from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sql import get_session
from app.core.templates import templates
from app.schemas.model import ModelCard
from app.schemas.user import UserCookie
from app.services.data_fetch import get_models_cards
from app.utils.dependencies import get_user_cookie

router = APIRouter()


@router.get("/models", name="models")
async def get_models(
    request: Request,
    user_cookie: UserCookie = Depends(get_user_cookie),
    session: AsyncSession = Depends(get_session),
):
    """Рендер страницы со списком моделей"""
    # Получение всех моделей пользователя
    models_cards: list[ModelCard] = await get_models_cards(user_cookie, session)

    # Рендер
    return templates.TemplateResponse(
        "pages/models.html",
        {
            "request": request,
            "user_cookie": user_cookie,
            "page": "models",
            "models": models_cards,
        },
    )
