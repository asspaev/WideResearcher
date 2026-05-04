import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, ResearchSettingsMixin


class ScheduleStatus(enum.Enum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"


class ResearchSchedule(ResearchSettingsMixin, Base):
    """ORM-модель расписания исследований"""

    # ID-параметры
    schedule_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    research_id: Mapped[int] = mapped_column(ForeignKey("researches.research_id"), nullable=False)

    # SCHEDULE-параметры
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    repeat_type: Mapped[str] = mapped_column(String, nullable=False)
    repeat_value: Mapped[int] = mapped_column(Integer, nullable=False)
    repeat_unit: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ScheduleStatus] = mapped_column(ENUM(ScheduleStatus, name="schedule_status_enum"), nullable=False)

    # RELATIONSHIPS
    research = relationship("Research", back_populates="schedules", foreign_keys=[research_id])
