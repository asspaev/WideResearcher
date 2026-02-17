from fastapi import APIRouter

from app.config import get_settings

from .auth import router as router_auth
from .models import router as router_models
from .researches import router as router_researches

router = APIRouter(prefix=get_settings().prefix.v1, tags=["v1"])

router.include_router(router_auth)

router.include_router(router_models)

router.include_router(router_researches)
