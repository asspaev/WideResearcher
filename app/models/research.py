import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.research_stages import RESEARCH_STAGES

from .base import Base, ResearchSettingsMixin


class ResearchStatus(enum.Enum):
    IN_PROCESS = "IN_PROCESS"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"


class MetaTrigger(enum.Enum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"


class Research(ResearchSettingsMixin, Base):
    """ORM-модель исследования"""

    # ID-параметры
    research_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)

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
    research_result_bm25_chunks: Mapped[dict | None] = mapped_column(JSONB)
    research_result_embed_summary: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    research_result_embed_chunks: Mapped[dict | None] = mapped_column(JSONB)
    research_result_rerank_chunks: Mapped[dict | None] = mapped_column(JSONB)
    research_error_body: Mapped[str | None] = mapped_column(Text)

    # META-параметры
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # RELATIONSHIPS
    user = relationship("User", back_populates="researches")
    parent = relationship("Research", remote_side=[research_id])
    schedules = relationship("ResearchSchedule", back_populates="research", foreign_keys="ResearchSchedule.research_id")
    outputs = relationship("ModelOutput", back_populates="research")
    page_summaries = relationship("ChunkSummary", back_populates="research")
