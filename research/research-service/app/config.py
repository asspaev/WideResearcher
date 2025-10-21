from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent


class PrefixConfig(BaseModel):
    api: str = "/api"
    v1: str = "/v1"
    research: str = "/research"


class DatabaseConfig(BaseModel):
    url: PostgresDsn
    user: str
    password: str
    database: str
    echo: bool = False
    echo_pool: bool = False
    max_overflow: int = 50
    pool_size: int = 50

    naming_convention: dict[str, str] = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.template", ".env"),
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    prefix: PrefixConfig = PrefixConfig()
    db: DatabaseConfig


@lru_cache()
def get_settings() -> Settings:
    return Settings()
