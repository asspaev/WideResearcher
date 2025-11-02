from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from loguru import logger

from app.api import router as router_api
from app.config import get_settings
from app.core.sql import get_sql


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Launch SQL ---
    logger.info("SQL client ready")
    # --- Yield to FastAPI ---
    try:
        logger.success("Application is running")
        yield
    finally:
        # --- Close SQL ---
        await get_sql().dispose()
        logger.info("SQL connections closed")
        logger.success("Application is stopped")

app = FastAPI(lifespan=lifespan)

app.include_router(router_api)


if __name__ == "__main__":
    uvicorn.run(app, host=get_settings().app.host, port=get_settings().app.port)
