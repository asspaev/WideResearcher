from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ChunkSummary(Base):
    """ORM-модель саммари чанка страницы для конкретного исследования."""

    __tablename__ = "chunk_summaries"
    __table_args__ = (UniqueConstraint("page_url", "research_id", "chunk_index"),)

    # ID-параметры
    chunk_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    page_url: Mapped[str] = mapped_column(Text, ForeignKey("scrapped_pages.page_url"), nullable=False)
    research_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("researches.research_id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # CONTENT
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    bm25_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=True)
    embed_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=True)
    rerank_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=True)
    page_embed: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    page_summary: Mapped[str] = mapped_column(Text, nullable=True)

    # RELATIONSHIPS
    scrapped_page = relationship("ScrappedPage", back_populates="summaries")
    research = relationship("Research", back_populates="page_summaries")
