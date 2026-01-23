from fastapi import APIRouter

from .auth import router as router_auth
from .index import router as router_index

router = APIRouter(tags=["web"])

router.include_router(router_index)

router.include_router(router_auth)
