from app.config import get_settings
from fastapi import APIRouter

from .v1 import router as v1_router

router = APIRouter(prefix=get_settings().prefix.api)

router.include_router(v1_router)
