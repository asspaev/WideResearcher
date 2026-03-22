from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix=get_settings().prefix.forms, tags=["forms"])
