from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ResearchEpoch(Base):
    """ORM-модель эпохи исследования"""

    # ID-параметры
    research_id: Mapped[int] = mapped_column(ForeignKey("researches.research_id"), primary_key=True)
    epoch_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # RESEARCH-параметры
    research_body_start: Mapped[dict] = mapped_column(JSONB, nullable=False)
    research_body_finish: Mapped[dict] = mapped_column(JSONB, nullable=False)
    research_direction_content: Mapped[str | None] = mapped_column(Text)
    research_search_keywords: Mapped[dict | None] = mapped_column(JSONB)
    research_result_search_links: Mapped[dict | None] = mapped_column(JSONB)

    # RELATIONSHIPS
    research = relationship("Research", back_populates="epochs")
