import time

from app.core.redis import get_redis

_TTL = 48 * 3600

STAGE_ORDER = [
    "LAUNCH",
    "DIRECTION",
    "KEYWORDS",
    "SEARCH",
    "SCRAPE",
    "SCORING_BM25",
    "SCORING_EMBED",
    "SCORING_RERANK",
    "SUMMARIZE",
    "STRUCTURE",
    "WRITE",
    "DONE",
]


async def save_stage_start(research_id: int, stage: str) -> None:
    """Сохраняет unix-timestamp начала стадии в Redis."""
    try:
        r = await get_redis()
        key = f"research:{research_id}:stage_timers"
        await r.hset(key, stage, str(time.time()))
        await r.expire(key, _TTL)
    except Exception:
        pass


async def get_stage_timers(research_id: int) -> dict[str, float]:
    """Читает словарь {stage: start_unix_ts} из Redis."""
    try:
        r = await get_redis()
        raw = await r.hgetall(f"research:{research_id}:stage_timers")
        return {k: float(v) for k, v in raw.items()}
    except Exception:
        return {}


def compute_ws_timers(
    stage_ts: dict[str, float],
    current_stage: str,
) -> tuple[dict[str, int], int]:
    """Вычисляет длительности завершённых стадий и секунды текущей стадии.

    Args:
        stage_ts: словарь {stage: start_unix_ts} из Redis.
        current_stage: текущая стадия исследования.

    Returns:
        Кортеж (timers, active_elapsed):
        - timers: {stage_name: seconds} для завершённых стадий;
        - active_elapsed: секунды, прошедшие с начала текущей стадии.
    """
    now = time.time()
    current_idx = STAGE_ORDER.index(current_stage) if current_stage in STAGE_ORDER else 0
    timers: dict[str, int] = {}

    for i in range(current_idx):
        stage = STAGE_ORDER[i]
        if stage not in stage_ts:
            continue
        end_ts: float | None = None
        for j in range(i + 1, len(STAGE_ORDER)):
            if STAGE_ORDER[j] in stage_ts:
                end_ts = stage_ts[STAGE_ORDER[j]]
                break
        if end_ts is not None:
            timers[stage] = round(end_ts - stage_ts[stage])

    active_elapsed = 0
    if current_stage in stage_ts:
        active_elapsed = round(now - stage_ts[current_stage])

    return timers, active_elapsed
