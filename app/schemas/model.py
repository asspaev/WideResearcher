from pydantic import BaseModel


class ModelBase(BaseModel):
    model_id: int
    model_name: str


class ModelCard(ModelBase):
    model_created_time: str
    model_used_count: int
