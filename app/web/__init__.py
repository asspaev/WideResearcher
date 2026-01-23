from fastapi import APIRouter

from .index import router as router_index

router = APIRouter(tags=["web"])

router.include_router(router_index)
