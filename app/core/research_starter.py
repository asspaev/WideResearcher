from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scenario.base import ScenarioBase
from app.core.scenario.normal import NormalScenario
from app.models.research import Research

SCENARIO_MAP: dict[str, type[ScenarioBase]] = {
    "NORMAL": NormalScenario,
}


async def start_research(session: AsyncSession, research: Research) -> None:
    """Определяет сценарий по типу в настройках исследования и запускает его.

    Args:
        session: Асинхронная сессия SQLAlchemy.
        research: ORM-объект исследования.

    Raises:
        ValueError: Если тип сценария не найден в SCENARIO_MAP.
    """
    scenario_key = research.settings_scenario_type.upper()
    scenario_cls = SCENARIO_MAP.get(scenario_key)

    if scenario_cls is None:
        raise ValueError(f"Unknown scenario type: {scenario_key!r}. Available: {list(SCENARIO_MAP)}")

    scenario: ScenarioBase = scenario_cls(
        session=session,
        research=research,
        prompt=research.research_body_start.get("prompt", ""),
    )

    await scenario.launch()
