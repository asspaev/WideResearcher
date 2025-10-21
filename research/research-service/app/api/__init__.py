from fastapi import APIRouter

from app.config import get_settings

from .v1 import router as v1_router

router = APIRouter(prefix=get_settings().prefix.v1.api)

router.include_router(v1_router)
