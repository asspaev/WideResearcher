from app.config import get_settings
from fastapi import APIRouter

router = APIRouter(prefix=get_settings().prefix.research)
