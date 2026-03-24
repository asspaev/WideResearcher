from app.core.celery import celery_app


@celery_app.task(name="research.run")
def run_research(research_id: int) -> None:
    # TODO: implement DeepResearch pipeline
    pass
