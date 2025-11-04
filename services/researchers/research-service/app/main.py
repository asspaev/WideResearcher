from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from loguru import logger

from app.api import router as router_api
from app.config import get_settings
from app.core.mongo import client as get_mongo
from app.core.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Launch MongoDB ---
    logger.info("MongoDB client ready")
    # --- Launch Redis ---
    await init_redis()
    logger.info("Redis client ready")
    # --- Yield to FastAPI ---
    try:
        logger.success("Application is running")
        yield
    finally:
        # --- Close MongoDB ---
        get_mongo().client.close()
        logger.info("MongoDB client closed")
        # --- Close Redis ---
        await close_redis()
        logger.info("Redis client closed")
        logger.success("Application is stopped")

app = FastAPI(lifespan=lifespan)

app.include_router(router_api)


if __name__ == "__main__":
    uvicorn.run(app, host=get_settings().app.host, port=get_settings().app.port)
