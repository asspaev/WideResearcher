from sqlalchemy import BigInteger, Float, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class PageSummary(Base):
    """ORM-модель саммари страницы для конкретного исследования."""

    __tablename__ = "page_summaries"

    # ID-параметры (составной PK)
    page_url: Mapped[str] = mapped_column(Text, ForeignKey("scrapped_pages.page_url"), primary_key=True)
    research_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("researches.research_id"), primary_key=True)

    # CONTENT
    bm25_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=True)
    embed_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=True)
    rerank_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=True)
    page_embed: Mapped[float | None] = mapped_column(Float(precision=53))
    page_summary: Mapped[str] = mapped_column(Text, nullable=False)

    # RELATIONSHIPS
    scrapped_page = relationship("ScrappedPage", back_populates="summaries")
    research = relationship("Research", back_populates="page_summaries")
