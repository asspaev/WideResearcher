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
    "SCORING_BM25": "SCORING_BM25",
    "SCORING_EMBED": "SCORING_EMBED",
    "SCORING_RERANK": "SCORING_RERANK",
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
    research_result_bm25_links: Mapped[dict | None] = mapped_column(JSONB)
    research_result_embed_summary: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    research_result_embed_links: Mapped[dict | None] = mapped_column(JSONB)
    research_result_rerank_links: Mapped[dict | None] = mapped_column(JSONB)
    research_error_body: Mapped[str | None] = mapped_column(Text)

    # SETTINGS-параметры
    settings_search_areas: Mapped[dict | None] = mapped_column(JSONB)
    settings_exclude_search_areas: Mapped[dict | None] = mapped_column(JSONB)
    settings_n_vectors: Mapped[int] = mapped_column(Integer, default=5, server_default="5", nullable=False)
    settings_n_search_queries: Mapped[int] = mapped_column(Integer, default=5, server_default="5", nullable=False)
    settings_n_top_pages: Mapped[int] = mapped_column(Integer, default=10, server_default="10", nullable=False)
    settings_n_bm25_pages: Mapped[int] = mapped_column(Integer, default=10, server_default="10", nullable=False)
    settings_n_embed_pages: Mapped[int] = mapped_column(Integer, default=10, server_default="10", nullable=False)
    settings_n_rerank_pages: Mapped[int] = mapped_column(Integer, default=10, server_default="10", nullable=False)
    settings_n_async_parse: Mapped[int] = mapped_column(Integer, default=3, server_default="3", nullable=False)
    settings_scenario_type: Mapped[str] = mapped_column(Text, default="normal", server_default="normal", nullable=False)

    # META-параметры
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # MODEL-параметры
    model_id_answer: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_id_search: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_id_direction: Mapped[int | None] = mapped_column(BigInteger)
    model_id_embed: Mapped[int | None] = mapped_column(BigInteger)
    model_id_reranker: Mapped[int | None] = mapped_column(BigInteger)

    # RELATIONSHIPS
    user = relationship("User", back_populates="researches")
    parent = relationship("Research", remote_side=[research_id])
    schedules = relationship("ResearchSchedule", back_populates="research")
    outputs = relationship("ModelOutput", back_populates="research")
    page_summaries = relationship("PageSummary", back_populates="research")
