import enum

from sqlalchemy import BigInteger, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ResearchStatus(enum.Enum):
    IN_PROCESS = "IN_PROCESS"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


class MetaTrigger(enum.Enum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"


class Research(Base):
    """ORM-модель исследования"""

    # ID-параметры
    research_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    research_parent_id: Mapped[int | None] = mapped_column(ForeignKey("researches.research_id"), nullable=True)

    # RESEARCH-параметры
    research_status: Mapped[ResearchStatus] = mapped_column(
        ENUM(ResearchStatus, name="research_status_enum"), nullable=False
    )
    research_name: Mapped[str] = mapped_column(Text, nullable=False)
    research_version_name: Mapped[str] = mapped_column(Text, nullable=False)
    research_body: Mapped[dict | None] = mapped_column(JSONB)

    # SETTINGS-параметры
    settings_search_areas: Mapped[dict | None] = mapped_column(JSONB)
    settings_exclude_search_areas: Mapped[dict | None] = mapped_column(JSONB)
    settings_epochs_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")

    # MODEL-параметры
    model_id_answer: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_id_search: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_id_direction: Mapped[int | None] = mapped_column(BigInteger)

    # RELATIONSHIPS
    user = relationship("User", back_populates="researches")
    parent = relationship("Research", remote_side=[research_id])
    epochs = relationship("ResearchEpoch", back_populates="research")
    schedules = relationship("ResearchSchedule", back_populates="research")
    outputs = relationship("ModelOutput", back_populates="research")
