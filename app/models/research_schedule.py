import enum
from datetime import datetime, timedelta

from sqlalchemy import BigInteger, DateTime, ForeignKey, Interval
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ScheduleStatus(enum.Enum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"


class ResearchSchedule(Base):
    """ORM-модель расписания исследований"""

    # ID-параметры
    schedule_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    research_id: Mapped[int] = mapped_column(ForeignKey("researches.research_id"), nullable=False)

    # SCHEDULE-параметры
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    repeat_interval: Mapped[timedelta | None] = mapped_column(Interval, nullable=True)
    status: Mapped[ScheduleStatus] = mapped_column(ENUM(ScheduleStatus, name="schedule_status_enum"), nullable=False)

    # RELATIONSHIPS
    research = relationship("Research", back_populates="schedules")
