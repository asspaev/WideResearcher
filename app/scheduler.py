import asyncio

from loguru import logger

from app.core.sql import get_sql
from app.crud.research_schedule import get_due_planned_schedules, mark_schedule_completed
from app.tasks.research import run_research


async def _tick() -> None:
    db = get_sql()
    async with db.session_factory() as session:
        schedules = await get_due_planned_schedules(session)
        for schedule in schedules:
            logger.info(f"scheduler: triggering research {schedule.research_id} (schedule {schedule.schedule_id})")
            run_research.delay(schedule.research_id, triggered_by="scheduler")
            await mark_schedule_completed(session, schedule.schedule_id)


async def main() -> None:
    logger.info("scheduler: started, polling every 60 seconds")
    while True:
        try:
            await _tick()
        except Exception as exc:
            logger.error(f"scheduler: tick failed — {exc}")
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
