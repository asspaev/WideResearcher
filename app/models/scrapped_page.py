import enum

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ScrapeStatus(enum.Enum):
    SUCCESS = "SUCCESS"
    IN_PROGRESS = "IN_PROGRESS"
    ERROR = "ERROR"


class ScrappedPage(Base):
    """ORM-модель спаршенной страницы"""

    # PAGE-параметры
    page_url: Mapped[str] = mapped_column(Text, primary_key=True)
    page_raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    page_clean_content: Mapped[str | None] = mapped_column(Text)
    page_scrapped_status: Mapped[ScrapeStatus] = mapped_column(
        ENUM(ScrapeStatus, name="scrape_status_enum"), nullable=False
    )
