from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Model


async def get_models_by_user_id(
    session: AsyncSession,
    user_id: int,
) -> list[Model]:
    """
    Возвращает все модели пользователя по user_id.
    """
    stmt = select(Model).where(Model.user_id == user_id)

    result = await session.execute(stmt)
    return result.scalars().all()


async def model_exists_by_user_and_name(
    session: AsyncSession,
    user_id: int,
    model_name: str,
) -> bool:
    """
    Проверяет, существует ли модель с указанным model_name у пользователя.
    Возвращает True, если запись есть, иначе False.
    """
    stmt = select(
        exists().where(
            Model.user_id == user_id,
            Model.model_name == model_name,
        )
    )

    result = await session.execute(stmt)
    return result.scalar()


async def create_model(
    session: AsyncSession,
    user_id: int,
    model_type: str,
    model_name: str,
    model_api_type: str | None = None,
    model_path: str | None = None,
    model_key_api: str | None = None,
    model_key_answer: str | None = None,
) -> Model:
    """
    Создаёт новую запись в таблице Model и возвращает объект модели.
    """
    new_model = Model(
        user_id=user_id,
        model_type=model_type,
        model_name=model_name,
        model_api_type=model_api_type,
        model_path=model_path,
        model_key_api=model_key_api,
        model_key_answer=model_key_answer,
    )

    session.add(new_model)
    await session.commit()
    await session.refresh(new_model)
    return new_model
