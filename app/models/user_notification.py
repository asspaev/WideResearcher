import enum

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class NotificationStatus(enum.Enum):
    UNCHECKED = "UNCHECKED"
    CHECKED = "CHECKED"


class UserNotification(Base):
    """ORM-модель уведомления"""

    # CHECK-параметры
    __table_args__ = (
        CheckConstraint(
            "(notification_title IS NOT NULL OR notification_subtitle IS NOT NULL)",
            name="ck_notification_title_or_subtitle_not_null",
        ),
    )

    # ID-параметры
    notification_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)

    # NOTIFICATION-параметры
    notification_title: Mapped[str | None] = mapped_column(Text)
    notification_subtitle: Mapped[str | None] = mapped_column(Text)
    notification_status: Mapped[NotificationStatus] = mapped_column(
        ENUM(NotificationStatus, name="notification_status_enum"), nullable=False
    )
    notification_link: Mapped[str | None] = mapped_column(Text)

    # RELATIONSHIPS
    user = relationship("User", back_populates="notifications")
