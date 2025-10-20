from functools import lru_cache
from pathlib import Path
from sys import prefix

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent


class PrefixConfig(BaseModel):
    api: str = "/api"
    v1: str = "/v1"
    research: str = "/research"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.template", ".env"),
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    prefix: PrefixConfig = PrefixConfig()


@lru_cache()
def get_settings() -> Settings:
    return Settings()
