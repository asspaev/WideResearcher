import bcrypt
import jwt

from app.config import get_settings


def encode_jwt(
    payload: dict,
    private_key: str = get_settings().auth.jwt_private_key,
    algorithm: str = get_settings().auth.algorithm,
) -> str:
    """Выпускает JWT-токен"""
    encoded: str = jwt.encode(
        payload,
        private_key,
        algorithm=algorithm,
    )
    return encoded


def decode_jwt(
    jwt_token: str | bytes,
    public_key: str = get_settings().auth.jwt_public_key,
    algorithm: str = get_settings().auth.algorithm,
):
    """Декодирует JWT-токен"""
    decoded: dict = jwt.decode(
        jwt_token,
        public_key,
        algorithms=[algorithm],
    )
    return decoded


def hash_password(password: str) -> bytes:
    """Хеширует пароль"""
    salt: bytes = bcrypt.gensalt()
    pwd_bytes: bytes = password.encode("utf-8")
    return bcrypt.hashpw(pwd_bytes, salt)


def validate_password(
    password: str,
    hashed_password: bytes,
) -> bool:
    """Проверяет пароль на соответствие хешу"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password)
