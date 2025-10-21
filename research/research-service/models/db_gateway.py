from collections.abc import AsyncGenerator
from functools import lru_cache

from app.config import get_settings
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


class DatabaseGateway:
    def __init__(
        self,
        url: str,
        echo: bool = False,
        echo_pool: bool = False,
        max_overflow: int = 10,
        pool_size: int = 5,
    ) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url=url,
            echo=echo,
            echo_pool=echo_pool,
            max_overflow=max_overflow,
            pool_size=pool_size,
        )
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def session_getter(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            yield session


@lru_cache()
def get_db_gateway() -> DatabaseGateway:
    return DatabaseGateway(
        url=get_settings().db.url,
        echo=get_settings().db.echo,
        echo_pool=get_settings().db.echo_pool,
        max_overflow=get_settings().db.max_overflow,
        pool_size=get_settings().db.pool_size,
    )
