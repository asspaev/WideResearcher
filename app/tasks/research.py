import asyncio

from celery.signals import worker_ready
from loguru import logger

from app.core.celery import celery_app
from app.core.redis import close_redis, init_redis
from app.core.research_starter import start_research
from app.core.sql import get_sql
from app.crud.research import get_research_by_id, get_stale_in_process_researches


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    asyncio.run(_resume_stale_researches())


@celery_app.task(name="research.run")
def run_research(research_id: int) -> None:
    asyncio.run(_run_research(research_id))


async def _run_research(research_id: int) -> None:
    await init_redis()
    try:
        db = get_sql()
        async with db.session_factory() as session:
            research = await get_research_by_id(session, research_id)
            if research is None:
                logger.error(f"run_research: research {research_id} not found")
                return

            await start_research(session, research)
    finally:
        await close_redis()


async def _resume_stale_researches() -> None:
    await init_redis()
    try:
        db = get_sql()
        async with db.session_factory() as session:
            stale = await get_stale_in_process_researches(session)
            for research in stale:
                logger.info(
                    f"worker_ready: resuming research {research.research_id} " f"from stage {research.research_stage}"
                )
                run_research.delay(research.research_id)
    finally:
        await close_redis()
