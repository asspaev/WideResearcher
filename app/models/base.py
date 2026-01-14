from sqlalchemy import Integer, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.config import get_settings
from app.utils import camel_case_to_snake_case


class Base(DeclarativeBase):
    __abstract__ = True

    metadata = MetaData(naming_convention=get_settings().sql.naming_convention)

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return camel_case_to_snake_case(cls.__name__)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
