from fastapi import APIRouter

from app.config import get_settings

from .predictions import router as router_predictions

router = APIRouter(prefix=get_settings().prefix.v1, tags=["v1"])

router.include_router(router_predictions)
