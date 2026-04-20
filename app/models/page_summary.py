from sqlalchemy import BigInteger, ForeignKey, ForeignKeyConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class PageSummary(Base):
    """ORM-модель саммари страницы для конкретного исследования и эпохи."""

    __tablename__ = "page_summaries"

    __table_args__ = (
        ForeignKeyConstraint(
            ["research_id", "epoch_id"],
            ["research_epoches.research_id", "research_epoches.epoch_id"],
        ),
    )

    # ID-параметры (составной PK)
    page_url: Mapped[str] = mapped_column(Text, ForeignKey("scrapped_pages.page_url"), primary_key=True)
    research_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("researches.research_id"), primary_key=True)
    epoch_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # CONTENT
    page_summary: Mapped[str] = mapped_column(Text, nullable=False)

    # RELATIONSHIPS
    scrapped_page = relationship("ScrappedPage", back_populates="summaries")
    research = relationship("Research", back_populates="page_summaries", overlaps="epoch")
    epoch = relationship("ResearchEpoch", back_populates="page_summaries", overlaps="research")
