# API эндпоинты

## `/api/v1/auth/`
| Метод | Путь | Действие |
|-------|------|----------|
| POST | `/api/v1/auth/login` | Логин → cookie `access_token` + `HX-Redirect: /main` |
| POST | `/api/v1/auth/register` | Регистрация → cookie + redirect |

Ошибки возвращают шаблон `partials/result_form.html` с `message` и `type="wrong"`.

## `/api/v1/models`
| Метод | Путь | Действие |
|-------|------|----------|
| POST | `/api/v1/models` | Создать модель → шаблон `popups/model_created.html` (+ обновлённый список) |
| PUT | `/api/v1/models/{model_id}` | Обновить → `popups/model_edited.html` |
| DELETE | `/api/v1/models/{model_id}` | Удалить → `popups/model_deleted.html` |

## `/api/v1/researches`
| Метод | Путь | Действие |
|-------|------|----------|
| POST | `/api/v1/researches/settings` | (stub, не реализован) |

## Web-роуты (`/`)
| Метод | Путь | Шаблон |
|-------|------|--------|
| GET | `/` | `pages/index.html` (дашборд) |
| GET | `/login` | `pages/login.html` |
| GET | `/register` | `pages/register.html` |
| GET | `/models` | `pages/models.html` |
| GET | `/researches` | `pages/researches.html` |

## Попапы (`/popups/`)
| Метод | Путь | Действие |
|-------|------|----------|
| GET | `/popups/hide` | Закрыть попап (OOB swap `hidden_popup_overlay.html`) |
| GET | `/popups/researches/new` | Попап создания исследования |
| GET | `/popups/researches/new/settings` | Настройки нового исследования (query: `previous_screen`) |
| GET | `/popups/models/new` | Попап создания модели |
| GET | `/popups/models/{model_id}/edit` | Попап редактирования модели |
| GET | `/popups/models/{model_id}/delete` | Попап подтверждения удаления |

## Формы (`/forms/`)
| Метод | Путь | Действие |
|-------|------|----------|
| GET | `/forms/model-options?model_type=api` | Поля для API-модели |
| GET | `/forms/model-options?model_type=vllm` | Поля для VLLM-модели |
