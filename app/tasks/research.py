import asyncio
import json

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.celery import celery_app
from app.core.sql import get_sql
from app.crud.model import get_model_by_id
from app.crud.model_output import create_model_output
from app.crud.research import get_research_by_id
from app.crud.research_epoch import (
    create_research_epoch,
    update_research_epoch_keywords,
    update_research_epoch_search_links,
)
from app.models.model_output import ModelResponseStatus
from app.models.research import Research
from app.services.llm_client import LLMClient
from app.services.prompts import (
    SearchResultScores,
    SearchResultToScore,
    build_direction_messages,
    build_relevance_messages,
    build_search_keywords_messages,
)
from app.services.searxng_client import SearXNGClient

SEARCH_RESULTS_PER_KEYWORD = 20


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

        # Шаг 1: брейншторм направлений исследования → сохраняем эпоху и вектор
        direction = await _step_direction_brainstorm(session, research)

        # Шаг 2: генерация поисковых запросов → сохраняем в research_search_keywords эпохи
        keywords = await _step_search_keywords(session, research, direction)

        # Шаг 3: поиск по каждому ключевому слову через SearXNG + оценка релевантности
        await _step_search(session, research, keywords, direction)


async def _step_direction_brainstorm(session: AsyncSession, research: Research) -> str:
    """Шаг 1: определение направления исследования.

    Выполняет один вызов model_id_direction и сохраняет результат
    в model_outputs (epoch_id=0, step_type="direction_brainstorm").

    Args:
        session: Активная сессия БД.
        research: ORM-объект исследования.

    Returns:
        Ответ модели или пустую строку при ошибке.
    """
    if research.model_id_direction is None:
        logger.warning(
            f"_step_direction_brainstorm: research {research.research_id} has no model_id_direction, skipping"
        )
        return ""

    model = await get_model_by_id(session, research.model_id_direction)
    if model is None:
        logger.error(f"_step_direction_brainstorm: direction model {research.model_id_direction} not found")
        return ""

    llm = LLMClient(
        model_name=model.model_api_model,
        base_url=model.model_base_url,
        api_key=model.model_key_api,
    )

    messages = build_direction_messages(query=research.research_name)

    status = ModelResponseStatus.COMPLETE
    output_payload: dict = {}
    direction_content: str | None = None

    try:
        result = await llm.generate(messages)
        output_payload = {"content": result}
        direction_content = result
        logger.info(f"_step_direction_brainstorm: done (research_id={research.research_id})")
    except Exception as exc:
        status = ModelResponseStatus.ERROR
        output_payload = {"error": str(exc)}
        logger.error(f"_step_direction_brainstorm: failed (research_id={research.research_id}): {exc}")

    await create_model_output(
        session=session,
        model_id=research.model_id_direction,
        research_id=research.research_id,
        epoch_id=0,
        step_type="direction_brainstorm",
        model_input={"messages": messages},
        model_output=output_payload,
        response_status=status,
    )

    await create_research_epoch(
        session=session,
        research_id=research.research_id,
        epoch_id=0,
        body_start={"query": research.research_name},
        body_finish={},
        direction_content=direction_content,
    )

    return direction_content or ""


async def _step_search_keywords(
    session: AsyncSession,
    research: Research,
    direction: str,
    n_keywords: int = 5,
) -> list[str]:
    """Шаг 2: генерация поисковых запросов для SearXNG.

    Вызывает model_id_search с темой и направлением исследования,
    парсит JSON-массив строк и сохраняет в research_search_keywords эпохи.

    Args:
        session: Активная сессия БД.
        research: ORM-объект исследования.
        direction: Результат шага direction_brainstorm.
        n_keywords: Количество поисковых запросов.

    Returns:
        Список поисковых запросов или пустой список при ошибке.
    """
    model = await get_model_by_id(session, research.model_id_search)
    if model is None:
        logger.error(f"_step_search_keywords: search model {research.model_id_search} not found")
        return []

    llm = LLMClient(
        model_name=model.model_api_model,
        base_url=model.model_base_url,
        api_key=model.model_key_api,
    )

    messages = build_search_keywords_messages(
        query=research.research_name,
        direction=direction,
        n_keywords=n_keywords,
    )

    status = ModelResponseStatus.COMPLETE
    output_payload: dict = {}
    keywords: list[str] = []

    try:
        result = await llm.generate(messages)
        keywords = json.loads(result)
        if not isinstance(keywords, list):
            raise ValueError(f"expected JSON array, got {type(keywords).__name__}")
        keywords = [str(k) for k in keywords]
        output_payload = {"keywords": keywords}
        logger.info(
            f"_step_search_keywords: generated {len(keywords)} keywords " f"(research_id={research.research_id})"
        )
    except Exception as exc:
        status = ModelResponseStatus.ERROR
        output_payload = {"error": str(exc)}
        logger.error(f"_step_search_keywords: failed (research_id={research.research_id}): {exc}")

    await create_model_output(
        session=session,
        model_id=research.model_id_search,
        research_id=research.research_id,
        epoch_id=0,
        step_type="search_keywords",
        model_input={"messages": messages},
        model_output=output_payload,
        response_status=status,
    )

    if keywords:
        await update_research_epoch_keywords(
            session=session,
            research_id=research.research_id,
            epoch_id=0,
            keywords=keywords,
        )

    return keywords


RELEVANCE_BATCH_SIZE = 10


async def _step_search(
    session: AsyncSession,
    research: Research,
    keywords: list[str],
    direction: str,
) -> None:
    """Шаг 3: поиск через SearXNG + оценка релевантности результатов.

    Для каждого ключевого слова выполняет поиск, затем отправляет результаты
    батчами по 10 в model_id_research для оценки релевантности по шкале 0.0–1.0.

    Args:
        session: Активная сессия БД.
        research: ORM-объект исследования.
        keywords: Список поисковых запросов из шага search_keywords.
        direction: Результат шага direction_brainstorm (векторы исследования).
    """
    if not keywords:
        logger.warning(f"_step_search: no keywords, skipping (research_id={research.research_id})")
        return

    settings = get_settings()
    client = SearXNGClient(base_url=settings.searxng.url)

    model = await get_model_by_id(session, research.model_id_search)
    llm: LLMClient | None = None
    if model is None:
        logger.warning(
            f"_step_search: search model {research.model_id_search} not found, "
            f"skipping relevance scoring (research_id={research.research_id})"
        )
    else:
        llm = LLMClient(
            model_name=model.model_api_model,
            base_url=model.model_base_url,
            api_key=model.model_key_api,
        )

    # (title, url, total_score) по всем keyword'ам
    scored_documents: list[tuple[str, str, float]] = []

    for keyword in keywords:
        try:
            results = await client.search(keyword, n_results=SEARCH_RESULTS_PER_KEYWORD)
            logger.debug(
                f"_step_search: keyword={keyword!r} → {len(results)} results " f"(research_id={research.research_id})"
            )
            for i, r in enumerate(results, 1):
                logger.debug(f"  [{i}] title={r.title!r} url={r.url!r} description={r.description!r}")
        except Exception as exc:
            logger.error(
                f"_step_search: failed for keyword={keyword!r} " f"(research_id={research.research_id}): {exc}"
            )
            continue

        if llm is None:
            continue

        # Оценка релевантности батчами по RELEVANCE_BATCH_SIZE
        for batch_start in range(0, len(results), RELEVANCE_BATCH_SIZE):
            batch = results[batch_start : batch_start + RELEVANCE_BATCH_SIZE]
            to_score = [SearchResultToScore(title=r.title, description=r.description) for r in batch]
            try:
                messages = build_relevance_messages(
                    query=research.research_name,
                    direction=direction,
                    keyword=keyword,
                    results=to_score,
                )
                raw = await llm.generate(messages)
                scores = [SearchResultScores(**item) for item in json.loads(raw)]
                logger.debug(
                    f"_step_search: relevance scores for keyword={keyword!r} "
                    f"batch={batch_start + 1}-{batch_start + len(batch)} "
                    f"(research_id={research.research_id})"
                )
                for idx, s in enumerate(scores):
                    result = batch[idx]
                    total = (
                        s.point_1
                        + s.point_2
                        + s.point_3
                        + s.point_4
                        + s.point_5
                        + s.point_6
                        + s.point_7
                        + s.point_8
                        + s.point_9
                        + s.point_10
                    )
                    scored_documents.append((result.title, result.url, total))
                    logger.debug(
                        f"  [{batch_start + idx + 1}] total={total:.1f} "
                        f"p1={s.point_1} p2={s.point_2} p3={s.point_3} p4={s.point_4} p5={s.point_5} "
                        f"p6={s.point_6} p7={s.point_7} p8={s.point_8} p9={s.point_9} p10={s.point_10}"
                    )
            except Exception as exc:
                logger.error(
                    f"_step_search: relevance scoring failed for keyword={keyword!r} "
                    f"batch={batch_start + 1}-{batch_start + len(batch)} "
                    f"(research_id={research.research_id}): {exc}"
                )

    if scored_documents:
        top10 = sorted(scored_documents, key=lambda x: x[2], reverse=True)[:10]
        logger.debug(f"_step_search: top-10 documents by total score (research_id={research.research_id})")
        for rank, (title, url, total) in enumerate(top10, 1):
            logger.debug(f"  #{rank} total={total:.1f} title={title!r} url={url!r}")

        await update_research_epoch_search_links(
            session=session,
            research_id=research.research_id,
            epoch_id=0,
            links=[{"title": title, "url": url, "total_score": total} for title, url, total in top10],
        )
