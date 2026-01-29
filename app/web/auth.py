from fastapi import APIRouter, Request
from loguru import logger

from app.core.templates import templates

router = APIRouter()


@router.get("/login", name="login")
async def get_login(request: Request):
    """Рендер страницы авторизации"""
    try:
        return templates.TemplateResponse("pages/login.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering login page: {e}")


@router.get("/register", name="register")
async def get_register(request: Request):
    """Рендер страницы регистрации"""
    try:
        return templates.TemplateResponse("pages/register.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering register page: {e}")
