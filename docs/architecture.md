# Архитектура проекта

```
app/
├── scheduler.py             # Планировщик: polling каждые 60 с, запуск дочерних исследований
├── api/v1/                  # REST API (JSON/HTML-фрагменты)
│   ├── auth.py              # POST /api/v1/auth/login, /register
│   ├── models.py            # POST/PUT/DELETE /api/v1/models[/{id}]
│   └── researches.py        # CRUD исследований, сегменты, планировщик (625 строк)
├── web/                     # Web-роуты (HTML через HTMX)
│   ├── index.py             # GET / — дашборд
│   ├── auth.py              # GET /login, /register
│   ├── models.py            # GET /models
│   ├── researches.py        # GET /researches, /researches/{id}
│   ├── wiki.py              # GET /wiki, /articles/{slug}
│   ├── popups.py            # GET /popups/* — попапы (OOB-свапы)
│   └── forms.py             # GET /forms/* — динамические фрагменты форм
├── models/                  # SQLAlchemy ORM модели
│   ├── base.py              # Base + ResearchSettingsMixin (settings_* + model_id_*)
│   ├── user.py              # User (users)
│   ├── model.py             # Model (models) — LLM конфигурации
│   ├── research.py          # Research (researches) — центральная сущность
│   ├── research_schedule.py # ResearchSchedule (research_schedules)
│   ├── model_output.py      # ModelOutput (model_outputs) — лог LLM-вызовов
│   ├── chunk_summary.py     # ChunkSummary (chunk_summaries) — чанки + скоры
│   ├── scrapped_page.py     # ScrappedPage (scrapped_pages)
│   └── user_notification.py # UserNotification (user_notifications)
├── schemas/                 # Pydantic схемы
│   ├── user.py              # UserCookie
│   ├── model.py             # ModelBase, ModelCard
│   └── research.py          # ResearchBase, ResearchCard, NearestResearch
├── crud/                    # Операции с БД
│   ├── user.py              # check_exists, create, get_by_login
│   ├── model.py             # get_by_user, exists, create, get_by_id, update, delete
│   ├── model_output.py      # create, update, count_by_model_id
│   ├── research.py          # get_all_with_schedules, get_by_id, create, update_*
│   ├── research_schedule.py # upsert, get, delete, get_due_planned, reschedule_next
│   └── scrapped_page.py     # get, upsert
├── services/                # Сервисы
│   ├── llm_client.py        # LLMClient — async OpenAI-compatible (generate/embed/structured)
│   ├── searxng_client.py    # SearXNGClient — HTTP-клиент для SearXNG JSON API
│   ├── web_scraper.py       # WebScraper — curl_cffi с Chrome TLS-отпечатком
│   ├── page_cleaner.py      # (не используется напрямую; очистка через trafilatura в search.py)
│   ├── prompts.py           # Все шаблоны промптов и build_*_messages() функции
│   └── data_fetch.py        # get_models_cards(), get_researches_cards(), get_research_detail()
├── core/                    # Инфраструктура и пайплайн исследования
│   ├── sql.py               # DatabaseGateway, get_sql(), get_session()
│   ├── redis.py             # redis_client, init_redis(), get_redis()
│   ├── redis_cache.py       # RedisCache (JSON-обёртка), get_redis_cache()
│   ├── celery.py            # celery_app, брокер = Redis
│   ├── templates.py         # templates (Jinja2Templates)
│   ├── research_starter.py  # start_research() — выбирает сценарий по settings_scenario_type
│   ├── research_stages.py   # STAGE_ORDER, STAGE_LABELS_*, RESEARCH_STATUS_LABELS
│   ├── research_timers.py   # save_stage_start(), get_stage_timers(), compute_ws_timers()
│   ├── scenario/            # Сценарии исследования
│   │   ├── base.py          # ScenarioBase: launch(), pipeline(), get_write_step()
│   │   ├── normal.py        # NormalScenario: все шаги pipeline (direction→...→rename)
│   │   └── question.py      # QuestionScenario: те же шаги, другой write-промпт
│   └── research/            # Шаги пайплайна
│       ├── base.py          # ResearchStepBase: _get_llm(), _log_extra()
│       ├── direction.py     # DirectionResearchStep — брейншторм через LLM
│       ├── keywords.py      # KeywordsResearchStep — генерация поисковых запросов
│       ├── search.py        # SearchResearchStep — SearXNG + scrape + clean
│       ├── chunking.py      # ChunkingResearchStep — нарезка страниц на чанки
│       ├── summarize.py     # SummarizeResearchStep — bullet-summary каждого чанка
│       ├── rename.py        # RenameResearchStep — короткое название через LLM
│       ├── scoring_pages/   # Скоринг чанков
│       │   ├── base.py      # ScoringPagesStepBase
│       │   ├── bm25.py      # BM25ScoringStep — TF-IDF без LLM
│       │   ├── embed.py     # EmbedScoringStep — косинусное сходство эмбеддингов
│       │   └── rerank.py    # RerankScoringStep — LLM оценивает релевантность [0..1]
│       └── write/           # Финальная запись результата
│           ├── base.py      # WriteStepBase
│           ├── standard.py  # StandardWriteStep — один LLM-вызов, Markdown → segments
│           └── segments.py  # format_as_segments(), apply_citations() — утилиты конвертации
├── tasks/                   # Celery задачи
│   └── research.py          # run_research — запускает research_starter.start_research()
├── utils/                   # Хелперы
│   ├── secrets.py           # encode_jwt, decode_jwt, hash_password, validate_password
│   ├── dependencies.py      # get_user_cookie() — FastAPI dependency
│   ├── middlewares.py       # AuthMiddleware
│   ├── validates.py         # validate_login, validate_password, validate_model_name
│   ├── datetime.py          # human_delta(), format_added_at() — русский язык
│   └── case_converter.py    # camel_case_to_snake_case() для именования таблиц
├── templates/               # Jinja2 шаблоны
│   ├── base.html            # Базовый layout (header, popup overlay, footer)
│   ├── pages/               # Полные страницы
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── models.html
│   │   ├── researches.html
│   │   ├── wiki.html        # Список статей wiki
│   │   └── article.html     # Отдельная статья wiki
│   └── includes/
│       ├── forms/           # Фрагменты форм
│       ├── popups/          # Попапы (HTMX)
│       ├── lists/           # Карточки моделей/исследований
│       └── svg/             # Иконки
├── alembic/                 # Миграции БД
├── config.py                # Pydantic Settings (SqlConfig, RedisConfig, AuthConfig, ...)
└── main.py                  # FastAPI lifespan, middleware, роутеры, static
```

---

## Важные детали реализации

### Datetime утилиты (`app/utils/datetime.py`)
- `human_delta(dt1, dt2) → str` — разница в человекочитаемом виде: `"21 день назад"`, `"через 12 недель"` (с правильными падежами)
- `format_added_at(dt) → str` — форматирует дату: `"12 октября 2024 года"` (через `babel.dates`, локаль `ru`)

### Redis (`app/core/redis.py` + `app/core/redis_cache.py`)
- Глобальный синглтон `redis_client`, инициализируется в lifespan
- Retry-логика: 5 попыток с экспоненциальным backoff
- `RedisCache` — обёртка для JSON-кэширования с TTL (по умолчанию 3600с)
- `get_redis()` — FastAPI dependency; `get_redis_cache()` — LRU-синглтон

### Конфигурация (`app/config.py`)
Классы настроек: `SqlConfig`, `RedisConfig`, `PrefixConfig`, `AppConfig`, `AuthConfig` — все собраны в `Settings`, читаются из `.env`.

### ResearchSettingsMixin (`app/models/base.py`)
Миксин, подключаемый к `Research` и `ResearchSchedule`. Содержит все настройки пайплайна:
`research_parent_id`, `settings_search_areas`, `settings_exclude_search_areas`, `settings_n_async_parse`, `settings_scenario_type`, `settings_n_vectors`, `settings_n_search_queries`, `settings_n_top_search_results`, `settings_n_top_bm25_chunks`, `settings_n_top_embed_chunks`, `settings_n_top_rerank_chunks`, `settings_n_top_chunks`, а также ссылки на модели: `model_id_answer`, `model_id_search`, `model_id_direction`, `model_id_embed`, `model_id_reranker`.

### Трекинг времени стадий (`app/core/research_timers.py`)
- `save_stage_start(research_id, stage)` — сохраняет unix-timestamp начала стадии в Redis (ключ `research:{id}:stage_timers`, TTL 48ч)
- `get_stage_timers(research_id)` — читает словарь `{stage: ts}` из Redis
- `compute_ws_timers(stage_ts, current_stage)` — вычисляет длительности завершённых стадий и секунды текущей для отображения в UI

### Планировщик (`app/scheduler.py`)
Отдельный процесс (Docker-контейнер `scheduler`). Каждые 60 секунд:
1. Запрашивает из БД все `ResearchSchedule` со статусом PLANNED и `scheduled_at <= now()`
2. Для каждого создаёт дочернее исследование (`create_scheduled_run`)
3. Отправляет Celery-задачу `research.run`
4. Вызывает `reschedule_next` — помечает текущую запись COMPLETED и создаёт новую PLANNED
