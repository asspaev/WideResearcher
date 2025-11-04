from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent


class RedisConfig(BaseModel):
    url: str
    host: str
    port: int
    connect_port: int = 6379
    password: str

    redis_db: int = 0
    pool_size: int = 100


class MongoConfig(BaseModel):
    url: str
    host: str
    port: int
    username: str
    password: str

    db_name: str = "mongo_db"
    pool_size: int = 100


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
        env_prefix="RESEARCH_SERVICE__",
        extra="ignore",
    )

    app: AppConfig
    prefix: PrefixConfig = PrefixConfig()
    mongo: MongoConfig
    redis: RedisConfig


@lru_cache()
def get_settings() -> Settings:
    return Settings()
