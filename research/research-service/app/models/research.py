from sqlalchemy import JSON, TIMESTAMP, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Research(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, comment="Research name")
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment="Research version")
    version_name: Mapped[str] = mapped_column(Text, comment="Version name")
    input: Mapped[dict] = mapped_column(JSON, comment="Input data")
    answer: Mapped[dict] = mapped_column(JSON, comment="Answer data")
    status: Mapped[str] = mapped_column(Text, comment="Research status")
    date_start: Mapped[str] = mapped_column(TIMESTAMP, nullable=False, comment="Start date of research")
    date_end: Mapped[str] = mapped_column(TIMESTAMP, comment="End date of research")
    model_query_generator: Mapped[int] = mapped_column(Integer, nullable=False, comment="ID of query generator model")
    model_extractor: Mapped[int] = mapped_column(Integer, nullable=False, comment="ID of extractor model")
    model_ummarizer: Mapped[int] = mapped_column(Integer, nullable=False, comment="ID of summarizer model")
