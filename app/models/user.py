from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    """ORM-модель пользователя"""

    # USER-параметры
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_login: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # RELATIONSHIPS
    researches = relationship("Research", back_populates="user")
    notifications = relationship("UserNotification", back_populates="user")
    models = relationship("Model", back_populates="user")
