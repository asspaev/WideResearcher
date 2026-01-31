from fastapi import APIRouter

from .auth import router as router_auth
from .forms import router as router_forms
from .index import router as router_index
from .models import router as router_models
from .popup import router as router_popup

router = APIRouter(tags=["web"])

router.include_router(router_index)

router.include_router(router_auth)

router.include_router(router_models)

router.include_router(router_popup)

router.include_router(router_forms)
