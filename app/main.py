from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api import router as router_api
from app.config import get_settings
from app.core.redis import close_redis, init_redis
from app.core.sql import get_sql
from app.web import router as router_web


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Launch Redis ---
    await init_redis()
    logger.info("Redis client ready")
    # --- Launch SQL ---
    logger.info("SQL client ready")
    # --- Yield to FastAPI ---
    try:
        logger.success("Application is running")
        yield
    finally:
        # --- Close Redis ---
        await close_redis()
        logger.info("Redis client closed")
        # --- Close SQL ---
        await get_sql().dispose()
        logger.info("SQL connections closed")
        logger.success("Application is stopped")


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(router_api)

app.include_router(router_web)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=get_settings().app.host, port=get_settings().app.port, reload=True)
