import asyncio

from loguru import logger

from app.core.celery import celery_app
from app.core.research_starter import start_research
from app.core.sql import get_sql
from app.crud.research import get_research_by_id


@celery_app.task(name="research.run")
def run_research(research_id: int) -> None:
    asyncio.run(_run_research(research_id))


async def _run_research(research_id: int) -> None:
    db = get_sql()
    async with db.session_factory() as session:
        research = await get_research_by_id(session, research_id)
        if research is None:
            logger.error(f"run_research: research {research_id} not found")
            return

        await start_research(session, research)
