# WideResearcher

Опенсорсный сервис глубокого поиска (Deep Researcher) с дружелюбным веб-интерфейсом. Собирает информацию из множества источников, итеративно уточняет её через систему лайков/дизлайков и структурирует результат в читаемый отчёт с цитатами по каждому сегменту.

**Ключевые отличия от аналогов:**
- Прозрачные источники — каждый сегмент результата привязан к конкретным URL с цитатами
- Итеративное уточнение — лайк/дизлайк на сегмент меняет поисковые запросы в следующей итерации
- Настройка через UI — >95% параметров задаётся в веб-интерфейсе, без правки конфигов
- Планировщик — автоматический повтор исследования по расписанию (daily, weekly, ...)

## Быстрый старт

**Требования:** Docker 24+, Docker Compose 2.20+

```bash
git clone https://github.com/your-org/wideresearcher.git
cd wideresearcher

cp .env.template .env
# Отредактировать .env: задать пароли и AUTH__JWT_PRIVATE_KEY / AUTH__JWT_PUBLIC_KEY

docker compose up -d
```

Откройте [http://localhost:6720](http://localhost:6720)

Порты по умолчанию:
| Сервис | Порт |
|--------|------|
| Приложение | 6720 |
| Redis | 6721 |
| PostgreSQL | 6722 |
| SearXNG | 6723 |

## Минимальная конфигурация `.env`

```env
AUTH__JWT_PRIVATE_KEY="<RSA private key PEM>"
AUTH__JWT_PUBLIC_KEY="<RSA public key PEM>"
REDIS__PASSWORD=your_redis_password
SQL__PASSWORD=your_pg_password
SEARXNG_SECRET_KEY=change_me_in_production
```

Все остальные настройки (LLM-модели, глубина поиска, сценарии) задаются в веб-интерфейсе после регистрации.

## Стек

Python 3.14 · FastAPI · SQLAlchemy 2.0 · PostgreSQL · Redis · Celery · HTMX · Docker

## Документация

| Документ | Описание |
|----------|----------|
| [`docs/architecture.md`](docs/architecture.md) | Дерево файлов и детали реализации |
| [`docs/data-models.md`](docs/data-models.md) | ORM-модели и Pydantic схемы |
| [`docs/api-endpoints.md`](docs/api-endpoints.md) | Все API-роуты |
| [`docs/research-pipeline.md`](docs/research-pipeline.md) | Каждый шаг пайплайна |
| [`docs/scenarios.md`](docs/scenarios.md) | Сценарии Normal и Question |
| [`docs/scheduler.md`](docs/scheduler.md) | Планировщик расписаний |
| [`docs/services.md`](docs/services.md) | Внешние сервисы (LLM, SearXNG, scraper) |
| [`docs/wiki/`](docs/wiki/) | Пользовательские руководства |

## Лицензия

MIT
