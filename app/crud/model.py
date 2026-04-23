from sqlalchemy import desc, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Model


async def get_models_by_user_id(
    session: AsyncSession,
    user_id: int,
    include_archived: bool = False,
) -> list[Model]:
    """
    Возвращает все модели пользователя по user_id.

    Args:
        include_archived: Если False (по умолчанию), исключает архивированные модели.
    """
    stmt = select(Model).where(Model.user_id == user_id)

    if not include_archived:
        stmt = stmt.where(Model.archived_at.is_(None))

    stmt = stmt.order_by(desc(Model.meta_updated_at))

    result = await session.execute(stmt)
    return result.scalars().all()


async def model_exists_by_user_and_name(
    session: AsyncSession,
    user_id: int,
    model_name: str,
    include_archived: bool = False,
) -> bool:
    """
    Проверяет, существует ли модель с указанным model_name у пользователя.
    Возвращает True, если запись есть, иначе False.

    Args:
        include_archived: Если False (по умолчанию), исключает архивированные модели.
    """
    conditions = [
        Model.user_id == user_id,
        Model.model_name == model_name,
    ]

    if not include_archived:
        conditions.append(Model.archived_at.is_(None))

    stmt = select(exists().where(*conditions))

    result = await session.execute(stmt)
    return result.scalar()


async def create_model(
    session: AsyncSession,
    user_id: int,
    model_name: str,
    model_type: str,
    model_base_url: str,
    model_api_model: str,
    model_key_api: str | None = None,
    model_max_tokens: int = 8000,
) -> Model:
    """
    Создаёт новую запись в таблице Model и возвращает объект модели.
    """
    new_model = Model(
        user_id=user_id,
        model_name=model_name,
        model_type=model_type,
        model_key_api=model_key_api,
        model_base_url=model_base_url,
        model_api_model=model_api_model,
        model_max_tokens=model_max_tokens,
    )

    session.add(new_model)
    await session.commit()
    await session.refresh(new_model)
    return new_model


async def get_model_by_id(
    session: AsyncSession,
    model_id: int,
    include_archived: bool = False,
) -> Model | None:
    """
    Возвращает модель по model_id.

    Args:
        include_archived: Если False (по умолчанию), исключает архивированные модели.
    """
    stmt = select(Model).where(Model.model_id == model_id)

    if not include_archived:
        stmt = stmt.where(Model.archived_at.is_(None))

    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_model(
    session: AsyncSession,
    model_id: int,
    *,
    model_name: str | None = None,
    model_key_api: str | None = None,
    model_base_url: str | None = None,
    model_api_model: str | None = None,
    model_max_tokens: int | None = None,
) -> Model | None:
    """
    Обновляет модель по model_id.
    Возвращает обновлённый объект Model или None, если модель не найдена.
    """

    result = await session.execute(select(Model).where(Model.model_id == model_id))
    model: Model | None = result.scalar_one_or_none()

    if model is None:
        return None

    if model_name is not None:
        model.model_name = model_name
    if model_key_api is not None:
        model.model_key_api = model_key_api
    if model_base_url is not None:
        model.model_base_url = model_base_url
    if model_api_model is not None:
        model.model_api_model = model_api_model
    if model_max_tokens is not None:
        model.model_max_tokens = model_max_tokens

    await session.commit()
    await session.refresh(model)
    return model


async def delete_model(
    session: AsyncSession,
    model_id: int,
) -> bool:
    """
    Архивирует модель по model_id (устанавливает archived_at = now()).
    Возвращает True, если модель найдена и архивирована, False если не найдена.
    """
    from datetime import datetime, timezone

    result = await session.execute(select(Model).where(Model.model_id == model_id))
    model: Model | None = result.scalar_one_or_none()

    if model is None:
        return False

    model.archived_at = datetime.now(timezone.utc)
    await session.commit()
    return True
