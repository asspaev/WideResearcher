from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from loguru import logger

from app.models import get_db_gateway
from app.routers import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    logger.info("Starting up database gateway...")
    yield
    # shutdown
    logger.info("Shutting down database gateway...")
    await get_db_gateway().dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8100, reload=True, log_level="info")
