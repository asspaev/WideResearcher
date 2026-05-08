# API эндпоинты

## `/api/v1/auth/`
| Метод | Путь | Действие | Ответ |
|-------|------|----------|-------|
| POST | `/api/v1/auth/login` | Логин → cookie `access_token` | 204 + `HX-Redirect: /` |
| POST | `/api/v1/auth/register` | Регистрация → cookie | 204 + `HX-Redirect: /` |

Ошибки: шаблон `partials/result_form.html` с `message` и `type="wrong"`.

## `/api/v1/models`
| Метод | Путь | Действие | Ответ |
|-------|------|----------|-------|
| POST | `/api/v1/models` | Создать модель | HTML: `popups/model_created.html` + OOB список |
| PUT | `/api/v1/models/{model_id}` | Обновить модель | HTML: `popups/model_edited.html` |
| DELETE | `/api/v1/models/{model_id}` | Удалить модель | HTML: `popups/model_deleted.html` |

## `/api/v1/researches`
| Метод | Путь | Действие | Ответ |
|-------|------|----------|-------|
| POST | `/api/v1/researches` | Создать исследование + запустить Celery | 204 + `HX-Redirect: /researches/{id}` |
| PUT | `/api/v1/researches/{id}` | Переименовать исследование | HTML: `popups/research_edited.html` + OOB список |
| PUT | `/api/v1/researches/{id}/version` | Переименовать версию | HTML: `popups/version_edited.html` |
| DELETE | `/api/v1/researches/{id}` | Архивировать исследование | HTML: `popups/research_deleted.html` + OOB список |
| POST | `/api/v1/researches/settings` | Сохранить настройки нового исследования в Redis | HTML-фрагмент попапа |
| POST | `/api/v1/researches/{id}/next-step/settings` | Сохранить настройки следующего этапа в Redis | HTML: `hidden_popup_step_settings.html` |
| POST | `/api/v1/researches/{id}/scheduler/settings` | Сохранить настройки планировщика в Redis | HTML: `hidden_popup_scheduler_settings.html` |
| POST | `/api/v1/researches/{id}/scheduler` | Сохранить расписание в БД | HTML: `popups/scheduler_saved.html` |
| DELETE | `/api/v1/researches/{id}/scheduler` | Удалить PLANNED расписание | HTML: `popups/scheduler_reset.html` |
| PATCH | `/api/v1/researches/{id}/segments/{index}` | Обновить поле сегмента (лайк/дизлайк/контент) | 204 |

### POST `/api/v1/researches` — параметры формы
Все параметры необязательны (заполняются из Redis-кэша настроек):
`prompt`, `model_answer`, `model_search`, `model_direction`, `model_embed`, `model_reranker`, `model_parent`, `n_async_parse`, `scenario_type`, `search_areas`, `exclude_search_areas`, `n_vectors`, `n_search_queries`, `n_top_search_results`, `n_top_bm25_chunks`, `n_top_embed_chunks`, `n_top_rerank_chunks`

### PATCH `/api/v1/researches/{id}/segments/{index}` — JSON body
```json
{
  "content": "string | null",
  "is_like": "bool | null",
  "is_dislike": "bool | null",
  "comment": "string | null"
}
```
Обновляет только переданные поля (`model_fields_set`).

## Web-роуты (`/`)
| Метод | Путь | Шаблон |
|-------|------|--------|
| GET | `/` | `pages/index.html` (дашборд) |
| GET | `/login` | `pages/login.html` |
| GET | `/register` | `pages/register.html` |
| GET | `/models` | `pages/models.html` |
| GET | `/researches` | `pages/researches.html` |
| GET | `/researches/{research_id}` | `pages/research.html` — детальная страница |
| GET | `/wiki` | `pages/wiki.html` — список статей |
| GET | `/articles/{slug}` | `pages/article.html` — отдельная статья |

## Попапы (`/popups/`)
| Метод | Путь | Действие |
|-------|------|----------|
| GET | `/popups/hide` | Закрыть попап (OOB swap `hidden_popup_overlay.html`) |
| GET | `/popups/researches/new` | Попап создания исследования |
| GET | `/popups/researches/new/settings` | Настройки нового исследования (`?previous_screen=...`) |
| GET | `/popups/researches/{id}/edit` | Переименование исследования |
| GET | `/popups/researches/{id}/version/edit` | Переименование версии |
| GET | `/popups/researches/{id}/delete` | Подтверждение архивирования |
| GET | `/popups/researches/{id}/scheduler` | Настройка расписания |
| GET | `/popups/researches/{id}/scheduler/settings` | Настройки исследования для планировщика |
| GET | `/popups/researches/{id}/next-step` | Запуск следующего этапа |
| GET | `/popups/researches/{id}/next-step/settings` | Настройки следующего этапа |
| GET | `/popups/models/new` | Попап создания модели |
| GET | `/popups/models/{model_id}/edit` | Попап редактирования модели |
| GET | `/popups/models/{model_id}/delete` | Попап подтверждения удаления |

## Формы (`/forms/`)
| Метод | Путь | Действие |
|-------|------|----------|
| GET | `/forms/model-options?model_type=api` | Поля для API-модели |
| GET | `/forms/model-options?model_type=vllm` | Поля для VLLM-модели |

---

## Соглашения

- **`/api/v1/*`** — возвращают HTML-фрагменты или 204; редиректы через `HX-Redirect` (код 204), не стандартный 302
- **`/`** (web-роуты) — полные HTML-страницы через Jinja2
- **`/popups/*`** — HTMX OOB-свапы (`hx-swap-oob="true"`), меняют `#popup-overlay`
- **`/forms/*`** — динамические фрагменты форм, подгружаются при смене типа модели
- Все защищённые роуты требуют cookie `access_token` (JWT RS256); при невалидном токене — 204 + `HX-Redirect: /login`
