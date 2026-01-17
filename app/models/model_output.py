import enum

from sqlalchemy import BigInteger, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ModelResponseStatus(enum.Enum):
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


class ModelOutput(Base):
    """ORM-модель выходных данных модели"""

    # ID-параметры
    response_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.model_id"), nullable=False)
    research_id: Mapped[int] = mapped_column(ForeignKey("researches.research_id"), nullable=False)
    epoch_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # OUTPUT-параметры
    response_status: Mapped[ModelResponseStatus] = mapped_column(
        ENUM(ModelResponseStatus, name="model_response_status_enum"), nullable=False
    )
    step_type: Mapped[str] = mapped_column(Text, nullable=False)
    model_input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_output: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # RELATIONSHIPS
    model = relationship("Model", back_populates="outputs")
    research = relationship("Research", back_populates="outputs")
