from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from loguru import logger

from app.core.templates import templates

router = APIRouter()


@router.get("/main", name="main", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "pages/main.html",
        {"request": request},
    )
