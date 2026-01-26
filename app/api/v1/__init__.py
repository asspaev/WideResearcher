from fastapi import APIRouter

from app.config import get_settings

from .auth import router as router_auth

router = APIRouter(prefix=get_settings().prefix.v1, tags=["v1"])

router.include_router(router_auth)
