from fastapi import APIRouter, Request

from app.config import get_settings

router = APIRouter(prefix=get_settings().prefix.researches, tags=["researches"])


@router.post("/settings", name="api_edit_new_research")
async def api_edit_new_research(request: Request):
    """Сохранение настроек нового исследования"""
    pass
