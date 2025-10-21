from fastapi import APIRouter

from app.config import get_settings

from .research import router as research_router

router = APIRouter(prefix=get_settings().prefix.prefix)

router.include_router(research_router)
