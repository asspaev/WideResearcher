from fastapi import HTTPException, Request
from loguru import logger

from app.schemas.user import UserCookie
from app.utils.secrets import decode_jwt


def get_user_cookie(request: Request) -> UserCookie:
    """Получение пользователя по JWT-токену"""
    try:
        session = request.cookies.get("access_token")
        access_token_data: dict = decode_jwt(session)
        user_cookie: UserCookie = UserCookie(
            user_id=access_token_data["user_id"],
            user_login=access_token_data["user_login"],
            meta_created_at=access_token_data["meta_created_at"],
        )
        return user_cookie
    except Exception as e:
        logger.debug(f"Error decoding JWT: {e}")
        raise HTTPException(
            status_code=401,
            headers={"HX-Redirect": "/login"},
        )
