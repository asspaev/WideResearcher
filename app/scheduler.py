import asyncio

from loguru import logger

from app.core.sql import get_sql
from app.crud.research import get_research_by_id
from app.crud.research_schedule import create_scheduled_run, get_due_planned_schedules, reschedule_next
from app.tasks.research import run_research


async def _tick() -> None:
    db = get_sql()
    async with db.session_factory() as session:
        schedules = await get_due_planned_schedules(session)
        for schedule in schedules:
            original = await get_research_by_id(session, schedule.research_id, include_archived=True)
            if original is None:
                logger.warning(f"scheduler: original research {schedule.research_id} not found, skipping")
                continue

            new_research = await create_scheduled_run(session, schedule, original)
            logger.info(
                f"scheduler: created research {new_research.research_id} "
                f"(type={schedule.repeat_type}, parent={new_research.research_parent_id})"
            )

            run_research.delay(new_research.research_id, triggered_by="scheduler")
            await reschedule_next(session, schedule)
            logger.info(
                f"scheduler: rescheduled {schedule.schedule_id} → {schedule.repeat_value} {schedule.repeat_unit}"
            )


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
