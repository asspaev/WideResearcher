from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger

from app.core.templates import templates

router = APIRouter()


@router.get("/", name="index", response_class=HTMLResponse)
async def index(request: Request):
    try:
        return RedirectResponse(url="/login")
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
