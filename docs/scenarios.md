# Сценарии исследования

## Что такое сценарий

Сценарий определяет, как именно пишется финальный ответ. Базовый класс `ScenarioBase` (`app/core/scenario/base.py`) содержит:
- `launch(resume)` — точка входа; запускает `pipeline()`, ловит ошибки, обновляет статус в БД
- `pipeline()` — абстрактный метод, реализуется в каждом сценарии
- `get_write_step()` — возвращает шаг Write по `settings_scenario_type` из `WRITE_MAP`
- `_should_skip_stage(stage)` — пропускает стадию если она уже пройдена (для resume)

Выбор сценария происходит в `app/core/research_starter.py`:

```python
SCENARIO_MAP = {
    "NORMAL": NormalScenario,
    "QUESTION": QuestionScenario,
}
scenario_cls = SCENARIO_MAP[research.settings_scenario_type.upper()]
```

---

## Normal сценарий (`app/core/scenario/normal.py`)

**Цель:** развёрнутое аналитическое исследование темы.

**Pipeline (порядок шагов):**
1. `DIRECTION` — LLM брейнштормит N векторов исследования
2. `KEYWORDS` — LLM генерирует N поисковых запросов
3. `SEARCH` — SearXNG поиск + scrape + clean
4. `SCRAPE` — нарезка на чанки (`ChunkingResearchStep`)
5. `SCORING_BM25` — TF-IDF фильтрация
6. `SCORING_EMBED` — фильтрация по косинусному сходству
7. `SCORING_RERANK` — LLM-скоринг релевантности
8. `SUMMARIZE` — bullet-summary каждого чанка
9. `WRITE` — `StandardWriteStep` с `build_write_normal_messages`: развёрнутый Markdown с разделами `##`, цитаты `[N]`
10. `RENAME` — LLM генерирует короткое название

**Когда использовать:** когда нужен структурированный обзор темы с анализом и выводами.

---

## Question сценарий (`app/core/scenario/question.py`)

**Цель:** краткий и точный ответ на конкретный вопрос.

**Pipeline:** идентичен Normal по шагам 1–8 и 10. Различие в шаге 9:
- `WRITE` — `StandardWriteStep` с `build_write_question_messages`: ответ 1–3 абзаца, без разделов `##`, с цитатами `[N]`

Промпт явно просит: «ответ по существу, без воды».

**Когда использовать:** когда нужен конкретный факт или ответ, а не развёрнутый обзор.

---

## Как добавить новый сценарий

1. Создать `app/core/scenario/my_scenario.py`, унаследовав от `ScenarioBase`
2. Реализовать `async def pipeline(self)` с нужным порядком шагов
3. Добавить промпт в `app/services/prompts.py` и при необходимости новый тип в `WRITE_MAP` в `base.py`
4. Зарегистрировать в `SCENARIO_MAP` в `app/core/research_starter.py`

---

## Настройки, влияющие на сценарий

Из `ResearchSettingsMixin` (хранятся в Research и ResearchSchedule):

| Поле | Влияние |
|------|---------|
| `settings_scenario_type` | Выбор класса сценария (`NORMAL` / `QUESTION`) |
| `settings_n_vectors` | Количество векторов в шаге DIRECTION |
| `settings_n_search_queries` | Количество поисковых запросов |
| `settings_n_top_search_results` | Результатов от SearXNG на запрос |
| `settings_n_top_bm25_chunks` | Топ-N после BM25 |
| `settings_n_top_embed_chunks` | Топ-N после Embed |
| `settings_n_top_rerank_chunks` | Топ-N после Rerank → идут в Write |
| `settings_search_areas` | Ограничить поиск доменами/URL |
| `settings_exclude_search_areas` | Исключить домены из поиска |
| `settings_n_async_parse` | Параллельность scraping |
| `model_id_answer` | Модель для Direction (при отсутствии direction), Summarize, Write, Rename |
| `model_id_search` | Модель для Keywords |
| `model_id_direction` | Модель для Direction (опционально) |
| `model_id_embed` | Модель для Embed-скоринга и Chunking (max_tokens) |
| `model_id_reranker` | Модель для Rerank-скоринга |
