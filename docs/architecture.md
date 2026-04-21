# Архитектура проекта

```
app/
├── api/v1/                  # REST API (JSON ответы)
│   ├── auth.py              # POST /api/v1/auth/login, /register
│   ├── models.py            # POST/PUT/DELETE /api/v1/models[/{id}]
│   └── researches.py        # (stub) POST /api/v1/researches/settings
├── web/                     # Web-роуты (HTML через HTMX)
│   ├── index.py             # GET / — дашборд
│   ├── auth.py              # GET /login, /register
│   ├── models.py            # GET /models
│   ├── researches.py        # GET /researches
│   ├── popups.py            # GET /popups/* — попапы (OOB-свапы)
│   └── forms.py             # GET /forms/* — динамические фрагменты форм
├── models/                  # SQLAlchemy ORM модели
│   ├── base.py              # Base: auto snake_case таблицы, meta_created_at/updated_at
│   ├── user.py              # User (users)
│   ├── model.py             # Model (models) — LLM конфигурации
│   ├── research.py          # Research (researches)
│   ├── research_epoch.py    # ResearchEpoch (research_epochs)
│   ├── research_schedule.py # ResearchSchedule (research_schedules)
│   ├── model_output.py      # ModelOutput (model_outputs)
│   ├── scrapped_page.py     # ScrappedPage (scrapped_pages)
│   └── user_notification.py # UserNotification (user_notifications)
├── schemas/                 # Pydantic схемы
│   ├── user.py              # UserCookie
│   ├── model.py             # ModelBase, ModelCard
│   └── research.py          # ResearchBase, ResearchCard, NearestResearch
├── crud/                    # Операции с БД
│   ├── user.py              # check_exists, create, get_by_login
│   ├── model.py             # get_by_user, exists, create, get_by_id, update, delete
│   ├── model_output.py      # count_by_model_id
│   └── research.py          # get_all_with_schedules, get_next_planned
├── services/                # Бизнес-логика
│   ├── data_fetch.py        # get_models_cards(), get_researches_cards()
│   └── llm_client.py        # LLMClient — async OpenAI-compatible client (generate)
├── core/                    # Инфраструктура
│   ├── sql.py               # DatabaseGateway, get_sql(), get_session()
│   ├── redis.py             # redis_client, init_redis(), get_redis()
│   ├── redis_cache.py       # RedisCache (JSON-обёртка), get_redis_cache()
│   └── templates.py         # templates (Jinja2Templates)
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
│   │   ├── index.html       # Дашборд
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── models.html
│   │   └── researches.html
│   └── includes/
│       ├── forms/           # Фрагменты форм
│       │   ├── new_research.html        # Быстрая форма создания исследования
│       │   ├── model_api_options.html   # Поля для API-модели
│       │   └── model_vllm_options.html  # Поля для VLLM-модели
│       ├── popups/          # Попапы (открываются через HTMX)
│       │   ├── new_research.html        # Создание исследования
│       │   ├── edit_new_research.html   # Настройки нового исследования
│       │   ├── new_model.html           # Создание модели
│       │   ├── edit_model.html          # Редактирование модели
│       │   ├── delete_model.html        # Подтверждение удаления
│       │   ├── model_created.html       # Успех создания
│       │   ├── model_edited.html        # Успех редактирования
│       │   └── model_deleted.html       # Успех удаления
│       ├── lists/
│       │   ├── list_models.html         # Карточки моделей
│       │   └── list_researches.html     # Карточки исследований
│       ├── header.html
│       ├── header-out-system.html       # Хедер для /login, /register
│       ├── hidden_popup_overlay.html    # OOB-свап закрытия попапа
│       ├── popup_close.html
│       ├── footer.html
│       └── svg/             # Иконки: logo, bell, delete, empty, git-fork,
│                            #   research, revert, settings, sort,
│                            #   start-research, timer, xmark
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
