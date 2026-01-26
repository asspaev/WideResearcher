from fastapi import Request
from fastapi.responses import Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.secrets import decode_jwt


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware для проверки access_token"""

    async def dispatch(self, request: Request, call_next):
        """Обработка запроса и возврат ответа"""

        # Разрешённые пути
        ALLOWED_PATHS = ["/login", "/register", "/api/v1/auth/login", "/api/v1/auth/register", "/static/"]

        # Пропускаем запросы к разрешённым путям
        for path in ALLOWED_PATHS:
            if request.url.path.startswith(path):
                return await call_next(request)

        # Достаём токен
        token: str | None = request.cookies.get("access_token")

        # Если нет токена, то возвращаем страницу логина
        try:
            decode_jwt(token)
        except Exception as e:
            logger.debug(f"Error decoding JWT: {e}")
            response: Response = Response(status_code=204)
            response.headers["HX-Redirect"] = "/login"
            return response

        # Возращаем ответ
        return await call_next(request)
