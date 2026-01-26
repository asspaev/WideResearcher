from fastapi import APIRouter

from .auth import router as router_auth
from .index import router as router_index
from .main import router as router_main

router = APIRouter(tags=["web"])

router.include_router(router_index)

router.include_router(router_auth)

router.include_router(router_main)
