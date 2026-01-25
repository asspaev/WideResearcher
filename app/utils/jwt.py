import jwt

from app.config import get_settings


def encode_jwt(
    payload: dict,
    private_key: str = get_settings().auth.jwt_private_key,
    algorithm: str = get_settings().auth.algorithm,
) -> str:
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
    decoded: dict = jwt.decode(
        jwt_token,
        public_key,
        algorithms=[algorithm],
    )
    return decoded
