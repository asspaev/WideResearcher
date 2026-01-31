from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent


class SqlConfig(BaseModel):
    url: str
    host: str
    port: int
    database: str
    user: str
    password: str
    max_overflow: int = 50
    pool_size: int = 50

    naming_convention: dict[str, str] = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


class RedisConfig(BaseModel):
    url: str
    host: str
    port: int
    connect_port: int = 6379
    password: str

    redis_db: int = 0
    pool_size: int = 100


class PrefixConfig(BaseModel):
    v1: str = "/v1"
    api: str = "/api"
    auth: str = "/auth"
    popup: str = "/popup"
    form: str = "/form"


class AppConfig(BaseModel):
    host: str
    port: int


class AuthConfig(BaseModel):
    jwt_private_key: str = "secret"
    jwt_public_key: str = "secret"
    algorithm: str = "RS256"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.template", ".env"),
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",
    )

    app: AppConfig
    prefix: PrefixConfig = PrefixConfig()
    redis: RedisConfig
    sql: SqlConfig
    auth: AuthConfig = AuthConfig()


@lru_cache()
def get_settings() -> Settings:
    return Settings()
