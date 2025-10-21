from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Status(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, comment="Status name")
    description: Mapped[str] = mapped_column(Text, comment="Status description")

    researches: Mapped[list["Research"]] = relationship("Research", back_populates="status")
