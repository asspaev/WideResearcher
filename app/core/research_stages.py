STAGE_ORDER: list[str] = [
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
    "RENAME",
    "DONE",
]

STAGE_LABELS_ACTIVE: dict[str, str] = {
    "LAUNCH": "Запускает исследование...",
    "DIRECTION": "Определяет направление...",
    "KEYWORDS": "Формирует поисковые запросы...",
    "SEARCH": "Ищет информацию...",
    "SCRAPE": "Собирает данные с сайтов...",
    "SCORING_BM25": "Оценивает по BM25...",
    "SCORING_EMBED": "Оценивает по эмбедингам...",
    "SCORING_RERANK": "Реранкирует результаты...",
    "SUMMARIZE": "Суммаризирует информацию...",
    "STRUCTURE": "Формирует структуру...",
    "WRITE": "Пишет исследование...",
    "RENAME": "Формирует название...",
    "DONE": "Завершено",
}

STAGE_LABELS_DONE: dict[str, str] = {
    "LAUNCH": "Запустил исследование",
    "DIRECTION": "Определил направление",
    "KEYWORDS": "Сформировал поисковые запросы",
    "SEARCH": "Нашёл информацию",
    "SCRAPE": "Собрал данные с сайтов",
    "SCORING_BM25": "Оценил по BM25",
    "SCORING_EMBED": "Оценил по эмбедингам",
    "SCORING_RERANK": "Реранкировал результаты",
    "SUMMARIZE": "Суммаризировал информацию",
    "STRUCTURE": "Сформировал структуру исследования",
    "WRITE": "Написал исследование",
    "RENAME": "Сформировал название",
    "DONE": "Завершено",
}

RESEARCH_STAGES: dict[str, str] = {s: s for s in STAGE_ORDER}
