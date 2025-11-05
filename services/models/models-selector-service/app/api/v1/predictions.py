from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.schemas.predictions import InputPredict, PredictionOutput
from app.services.predictions import run_predict

router = APIRouter(prefix=get_settings().prefix.predictions, tags=["v1"])


@router.post("")
async def predict(input_predict: InputPredict) -> PredictionOutput:
    try:
        result = await run_predict(input_predict)
        return result
    # TODO add more specific exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error. Error: {str(e)}")
