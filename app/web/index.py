from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.core.templates import templates

router = APIRouter()


@router.get("/", name="index", response_class=RedirectResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "pages/index.html",
        {"request": request},
    )
