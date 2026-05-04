from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, MetaData, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.config import get_settings
from app.utils import camel_case_to_snake_case


class ResearchSettingsMixin:
    research_parent_id: Mapped[int | None] = mapped_column(ForeignKey("researches.research_id"), nullable=True)

    # SETTINGS-параметры
    settings_search_areas: Mapped[str | None] = mapped_column(Text)
    settings_exclude_search_areas: Mapped[str | None] = mapped_column(Text)
    settings_n_async_parse: Mapped[int] = mapped_column(Integer, default=3, server_default="3", nullable=False)
    settings_scenario_type: Mapped[str] = mapped_column(Text, default="NORMAL", server_default="NORMAL", nullable=False)
    settings_n_vectors: Mapped[int] = mapped_column(Integer, default=5, server_default="5", nullable=False)
    settings_n_search_queries: Mapped[int] = mapped_column(Integer, default=5, server_default="5", nullable=False)
    settings_n_top_search_results: Mapped[int] = mapped_column(Integer, default=10, server_default="10", nullable=False)
    settings_n_top_bm25_chunks: Mapped[int] = mapped_column(Integer, default=50, server_default="50", nullable=False)
    settings_n_top_embed_chunks: Mapped[int] = mapped_column(Integer, default=30, server_default="30", nullable=False)
    settings_n_top_rerank_chunks: Mapped[int] = mapped_column(Integer, default=15, server_default="15", nullable=False)
    settings_n_top_chunks: Mapped[int] = mapped_column(Integer, default=15, server_default="15", nullable=False)

    # MODEL-параметры
    model_id_answer: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_id_search: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model_id_direction: Mapped[int | None] = mapped_column(BigInteger)
    model_id_embed: Mapped[int | None] = mapped_column(BigInteger)
    model_id_reranker: Mapped[int | None] = mapped_column(BigInteger)


class Base(DeclarativeBase):
    __abstract__ = True

    metadata = MetaData(naming_convention=get_settings().sql.naming_convention)

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return camel_case_to_snake_case(cls.__name__)

    # META-параметры
    meta_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    meta_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
