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


class PrefixConfig(BaseModel):
    v1: str = "/v1"
    api: str = "/api"


class AppConfig(BaseModel):
    host: str
    port: int


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.template", ".env"),
        case_sensitive=False,
        env_nested_delimiter="__",
        env_prefix="QUERY_GENERATOR_SERVICE__",
        extra="ignore",
    )

    app: AppConfig
    prefix: PrefixConfig = PrefixConfig()
    sql: SqlConfig


@lru_cache()
def get_settings() -> Settings:
    return Settings()
