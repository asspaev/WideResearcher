import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

RESEARCH_STAGES: dict[str, str] = {
    "LAUNCH": "LAUNCH",
    "DIRECTION": "DIRECTION",
    "KEYWORDS": "KEYWORDS",
    "SEARCH": "SEARCH",
    "SCRAPE": "SCRAPE",
    "SUMMARIZE": "SUMMARIZE",
    "STRUCTURE": "STRUCTURE",
    "WRITE": "WRITE",
    "DONE": "DONE",
}


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
    research_stage: Mapped[str] = mapped_column(Text, nullable=False)
    research_name: Mapped[str] = mapped_column(Text, nullable=False)
    research_version_name: Mapped[str] = mapped_column(Text, nullable=False)
    research_body_start: Mapped[dict | None] = mapped_column(JSONB)
    research_body_finish: Mapped[dict | None] = mapped_column(JSONB)
    research_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    research_direction_content: Mapped[str | None] = mapped_column(Text)
    research_search_keywords: Mapped[dict | None] = mapped_column(JSONB)
    research_result_search_links: Mapped[dict | None] = mapped_column(JSONB)

    # SETTINGS-параметры
    settings_search_areas: Mapped[dict | None] = mapped_column(JSONB)
    settings_exclude_search_areas: Mapped[dict | None] = mapped_column(JSONB)

    # META-параметры
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # MODEL-параметры
    model_id_answer: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_id_search: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_id_direction: Mapped[int | None] = mapped_column(BigInteger)

    # RELATIONSHIPS
    user = relationship("User", back_populates="researches")
    parent = relationship("Research", remote_side=[research_id])
    schedules = relationship("ResearchSchedule", back_populates="research")
    outputs = relationship("ModelOutput", back_populates="research")
    page_summaries = relationship("PageSummary", back_populates="research")
