# Celery в WideResearcher

## Архитектура

| Компонент | Контейнер | Назначение |
|-----------|-----------|-----------|
| Worker | `wideresearcher-celery-worker` | Выполняет задачи из очереди |
| Beat | `wideresearcher-celery-beat` | Планировщик — запускает задачи по расписанию |
| Broker | Redis db=1 | Очередь задач |
| Backend | Redis db=2 | Хранение результатов задач |

Redis db=0 занят кэшем приложения (`RedisCache`).

## Файлы

```
app/
├── core/
│   └── celery.py        # Инициализация celery_app
└── tasks/
    ├── __init__.py
    └── research.py      # Задача run_research(research_id)
```

## Добавление новых задач

Создать файл в `app/tasks/`, зарегистрировать модуль в `app/core/celery.py`:

```python
# app/core/celery.py
celery_app = Celery(
    ...
    include=["app.tasks.research", "app.tasks.my_new_module"],
)
```

Пример задачи:

```python
from app.core.celery import celery_app

@celery_app.task(name="research.run")
def run_research(research_id: int) -> None:
    ...
```

Вызов задачи из FastAPI-роута:

```python
from app.tasks.research import run_research

run_research.delay(research_id=42)
```

## Запуск

### Docker
```bash
docker-compose up --build
```
Поднимает 5 контейнеров: app, redis, postgres, celery-worker, celery-beat.

### Локально
```bash
# Worker
poetry run celery -A app.core.celery:celery_app worker --loglevel=info

# Beat (отдельный терминал)
poetry run celery -A app.core.celery:celery_app beat --loglevel=info
```

## Диагностика

```bash
# Активные воркеры
docker exec wideresearcher-celery-worker celery -A app.core.celery:celery_app inspect active

# Статус
docker exec wideresearcher-celery-worker celery -A app.core.celery:celery_app status

# Логи
docker logs wideresearcher-celery-worker
docker logs wideresearcher-celery-beat
```
