from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from loguru import logger

router = APIRouter()


@router.get("/", name="index", response_class=RedirectResponse)
async def index(request: Request):
    try:
        return RedirectResponse(url="/main")
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
