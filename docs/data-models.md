# Модели данных

## User (`users`)
```
user_id          BigInteger PK autoincrement
user_login       String(32) unique
user_password_hash LargeBinary (bcrypt)
→ researches, notifications, models
```

## Model (`models`) — конфигурация LLM
```
model_id         BigInteger PK
user_id          FK → users
model_type       Text  ("generative" | "embedding")
model_name       String(120)
model_api_type   Text  (опционально)
model_path       Text  (опционально, для vllm)
model_key_api    Text  (опционально)
model_key_answer Text  (опционально)
model_max_tokens Integer — используется ChunkingResearchStep для размера чанков
→ outputs (ModelOutput)
```

## Research (`researches`) — центральная сущность
Включает `ResearchSettingsMixin` (см. ниже).
```
research_id                      BigInteger PK
user_id                          FK → users
research_status                  ENUM: IN_PROCESS | COMPLETE | ERROR
research_stage                   Text — текущая стадия пайплайна (LAUNCH..DONE)
research_name                    Text
research_version_name            Text (например: "Версия 1", "Авто (продолжение)")
research_body_start              JSONB ({query: "..."})
research_body_finish             JSONB ({segments: [...]})
research_duration_seconds        Integer (опционально)
research_direction_content       Text — результат шага direction
research_search_keywords         JSONB — список поисковых запросов
research_result_search_links     JSONB — [{url: "..."}]
research_result_bm25_chunks      JSONB — [{chunk_id, page_url, chunk_index, bm25_score}]
research_result_embed_summary    JSONB — вектор эмбеддинга запроса + direction
research_result_embed_chunks     JSONB — [{chunk_id, page_url, chunk_index, embed_score}]
research_result_rerank_chunks    JSONB — [{chunk_id, page_url, chunk_index, rerank_score}]
research_error_body              Text (опционально)
archived_at                      DateTime with TZ (опционально)
→ schedules (ResearchSchedule), outputs (ModelOutput), page_summaries (ChunkSummary)
```
Плюс все поля из `ResearchSettingsMixin`.

## ResearchSettingsMixin (подмешивается в Research и ResearchSchedule)
```
research_parent_id               FK → researches (опционально)
settings_search_areas            Text (запятая-разделённые домены/URL)
settings_exclude_search_areas    Text
settings_n_async_parse           Integer default=3
settings_scenario_type           Text default="NORMAL"
settings_n_vectors               Integer default=5
settings_n_search_queries        Integer default=5
settings_n_top_search_results    Integer default=10
settings_n_top_bm25_chunks       Integer default=50
settings_n_top_embed_chunks      Integer default=30
settings_n_top_rerank_chunks     Integer default=15
settings_n_top_chunks            Integer default=15
model_id_answer                  BigInteger (not null)
model_id_search                  BigInteger (not null)
model_id_direction               BigInteger (опционально)
model_id_embed                   BigInteger (опционально)
model_id_reranker                BigInteger (опционально)
```

## ResearchSchedule (`research_schedules`) — планировщик
Включает `ResearchSettingsMixin`.
```
schedule_id      BigInteger PK autoincrement
research_id      FK → researches (не уникален — хранится история запусков)
scheduled_at     DateTime with TZ — время следующего запуска
repeat_type      Text ("start" | "current" | "deep")
repeat_value     Integer — числовое значение интервала
repeat_unit      Text ("minutes" | "hours" | "days" | "weeks" | "months" | "years")
status           ENUM: PLANNED | COMPLETED
```
Плюс все поля из `ResearchSettingsMixin` — настройки, с которыми будет запущено дочернее исследование.

Типы `repeat_type`:
- `start` — каждый раз начинает с нуля (без parent_id)
- `current` — продолжает текущее исследование (parent_id = original)
- `deep` — углубляет цепочку (parent_id = последнее автосозданное)

## ModelOutput (`model_outputs`) — лог LLM-вызовов
```
response_id      BigInteger PK
model_id         FK → models
research_id      FK → researches
response_status  ENUM: PROCESSING | COMPLETE | ERROR
step_type        Text — тип шага: "direction_brainstorm", "search_keywords", "write_normal", ...
model_input      JSONB — входные данные (messages / text)
model_output     JSONB — ответ модели
error_body       Text (опционально)
```

## ChunkSummary (`chunk_summaries`) — чанки страниц
```
chunk_id         BigInteger PK autoincrement
page_url         Text FK → scrapped_pages
research_id      BigInteger FK → researches
chunk_index      Integer — порядковый номер чанка в странице
chunk_content    Text — текст чанка
bm25_score       Numeric(4,3) — нормализованный [0..1] BM25-скор
embed_score      Numeric(4,3) — косинусное сходство с эмбеддингом запроса
rerank_score     Numeric(4,3) — релевантность по reranker-модели [0..1]
page_embed       JSONB — вектор эмбеддинга чанка (кэш)
page_summary     Text — bullet-point суммари от LLM (кэш)
UNIQUE (page_url, research_id, chunk_index)
```

## ScrappedPage (`scrapped_pages`) — кэш скрапинга
```
page_url              Text PK
page_raw_content      Text
page_clean_content    Text (опционально)
page_scrapped_status  ENUM: SUCCESS | IN_PROGRESS | ERROR
```

## UserNotification (`user_notifications`)
```
notification_id       BigInteger PK
user_id               FK → users
notification_title    Text (опционально)
notification_subtitle Text (опционально)
notification_status   ENUM: UNCHECKED | CHECKED
notification_link     Text (опционально)
CHECK: title IS NOT NULL OR subtitle IS NOT NULL
```

---

## Pydantic схемы

```python
# app/schemas/user.py
UserCookie: user_id, user_login, meta_created_at

# app/schemas/model.py
ModelBase: model_id, model_name
ModelCard(ModelBase): model_type (str), model_created_time (str), model_used_count (int)

# app/schemas/research.py
ResearchBase: research_id, research_name
ResearchCard(ResearchBase): research_status, research_stage, research_version_name,
                             research_last_update_time, schedule_next_launch_time
NearestResearch(ResearchBase): schedule_next_launch_time
```

Все схемы с `model_config = ConfigDict(from_attributes=True)`.

### Счётчик использования моделей
`ModelOutput` связывает модель с конкретным вызовом. `model_used_count` в `ModelCard` = `count_model_outputs_by_model_id(session, model_id)` из `app/crud/model_output.py`.

### JSONB поля
`Research.research_body_finish`, `research_body_start`, `research_result_*` — JSONB в PostgreSQL. SQLAlchemy 2.0+ сериализует автоматически, дополнительных преобразований не нужно.
