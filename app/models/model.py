from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Model(Base):
    """ORM-модель модели"""

    # ID-параметры
    model_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)

    # MODEL-параметры
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model_key_api: Mapped[str | None] = mapped_column(Text)
    model_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    model_api_model: Mapped[str] = mapped_column(Text, nullable=False)

    # META-параметры
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # RELATIONSHIPS
    user = relationship("User", back_populates="models")
    outputs = relationship("ModelOutput", back_populates="model")
