from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ResearchEpoch


async def create_research_epoch(
    session: AsyncSession,
    research_id: int,
    epoch_id: int,
    body_start: dict,
    body_finish: dict,
    direction_content: str | None = None,
) -> ResearchEpoch:
    record = ResearchEpoch(
        research_id=research_id,
        epoch_id=epoch_id,
        research_body_start=body_start,
        research_body_finish=body_finish,
        research_direction_content=direction_content,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
