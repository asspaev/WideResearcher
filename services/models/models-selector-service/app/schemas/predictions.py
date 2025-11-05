from enum import Enum

from pydantic import BaseModel, Field


class PredictionType(str, Enum):
    query = "query"
    extract = "extract"
    summarize = "summarize"


class InputPredict(BaseModel):
    predict_id: int | None = Field(default=1, description="Unique identifier for the prediction")
    prompt: str = Field("Write sample history", description="Prompt for text generation")
    type: PredictionType = Field(default=PredictionType.query, description="Type of prediction")
    max_tokens: int = Field(default=50, description="Maximum number of tokens to generate")
    temperature: float = Field(default=0.7, description="Temperature for text generation")


class LoadModelRequest(BaseModel):
    model_path: str
    dtype: str = "float16"


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 50
    temperature: float = 0.7


class PredictionOutput(BaseModel):
    request_id: int | None = None
    prompt: str | None = None
    text: str
    stop_reason: str | None = None
