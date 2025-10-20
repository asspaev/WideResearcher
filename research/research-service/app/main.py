import uvicorn
from app.routers import router as api_router
from fastapi import FastAPI

app = FastAPI()

app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True, log_level="info")
