from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def check_user_exists_by_login(
    session: AsyncSession,
    login: str,
) -> bool:
    """Проверяет существует ли пользователь с таким логином в базе данных"""
    stmt = select(exists().where(User.user_login == login))

    result = await session.execute(stmt)
    return result.scalar()


async def create_user(
    session: AsyncSession,
    login: str,
    hashed_password: bytes,
) -> User:
    """Создает пользователя в базе данных"""
    user = User(
        user_login=login,
        user_password_hash=hashed_password,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def get_user_by_login(
    session: AsyncSession,
    login: str,
) -> User | None:
    """Получает пользователя из базы данных по логину"""
    stmt = select(User).where(User.user_login == login)

    result = await session.execute(stmt)
    return result.scalar_one_or_none()
