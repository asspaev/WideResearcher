from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.sql import get_session
from app.core.templates import templates
from app.crud.user import check_user_exists_by_login, create_user, get_user_by_login
from app.models import User
from app.utils.secrets import encode_jwt, hash_password, validate_password
from app.utils.validates import validate_confirmation_password, validate_correct_password, validate_corrent_login

router = APIRouter(prefix=get_settings().prefix.auth, tags=["auth"])


@router.post("/login", name="api_login")
async def login(
    request: Request,
    login: str | None = Form(...),
    password: str | None = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Авторизация пользователя"""

    # Достать запись из БД по логину
    try:
        user: User | None = await get_user_by_login(session, login)
    except Exception as e:
        logger.error(f"Error getting user by login: {e}")
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": "Произошла ошибка при поиски пользователя в базе данных!",
                "type": "wrong",
            },
        )

    # Проверить, есть ли такой пользователь
    if not user:
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": "Пользователь не найден!",
                "type": "wrong",
            },
        )

    # Проверить, совпадает ли пароль
    if not validate_password(password, user.user_password_hash):
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": "Неверный пароль!",
                "type": "wrong",
            },
        )

    # Создание токена
    payload: dict = {
        "user_id": user.user_id,
        "user_login": user.user_login,
        "meta_created_at": str(user.meta_created_at),
    }
    jwt_token: str = encode_jwt(payload)

    # Создание ответа
    response: Response = Response(status_code=204)

    # Установка cookies
    response.set_cookie(key="access_token", value=jwt_token)

    # Установка headers
    response.headers["HX-Redirect"] = "/main"

    # Вернуть ответ
    return response


@router.post("/register", name="api_register")
async def register(
    request: Request,
    login: str | None = Form(...),
    password: str | None = Form(...),
    password_confirm: str | None = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Регистрация пользователя"""

    # Проверка совпадения паролей
    if not validate_confirmation_password(password, password_confirm):
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": "Пароли не совпадают!",
                "type": "wrong",
            },
        )

    # Проверка на уникальность логина
    if await check_user_exists_by_login(session, login):
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": "Пользователь с таким логином уже существует!",
                "type": "wrong",
            },
        )

    # Проверка на валидность логина
    correct_login: str | None = validate_corrent_login(login)
    if correct_login:
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": correct_login,
                "type": "wrong",
            },
        )

    # Проверка на валидность пароля
    correct_pasword: str | None = validate_correct_password(password)
    if correct_pasword:
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": correct_pasword,
                "type": "wrong",
            },
        )

    # Хеширование пароля
    hashed_password: bytes = hash_password(password)

    # Создание записи в базе данных
    try:
        user: User = await create_user(session, login, hashed_password)
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return templates.TemplateResponse(
            "partials/result_form.html",
            {
                "request": request,
                "message": "Произошла ошибка при сохранении пользователя в базу данных!",
                "type": "wrong",
            },
        )

    # Создание токена
    payload: dict = {
        "user_id": user.user_id,
        "user_login": user.user_login,
        "meta_created_at": str(user.meta_created_at),
    }
    jwt_token: str = encode_jwt(payload)

    # Создание ответа
    response: Response = Response(status_code=204)

    # Установка cookies
    response.set_cookie(key="access_token", value=jwt_token)

    # Установка headers
    response.headers["HX-Redirect"] = "/main"

    # Вернуть ответ
    return response
