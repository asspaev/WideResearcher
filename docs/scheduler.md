# Планировщик исследований

## Что такое планировщик

`app/scheduler.py` — отдельный async-процесс, который периодически проверяет таблицу `research_schedules` и запускает дочерние исследования по расписанию.

---

## Архитектура

Планировщик работает как **отдельный Docker-контейнер** (`scheduler` в `docker-compose.yml`):
```yaml
scheduler:
  build: .
  command: ["python", "-m", "app.scheduler"]
  depends_on: [redis, postgres]
```

Polling-цикл (`main()`):
```
while True:
    await _tick()        # обрабатывает все просроченные расписания
    await asyncio.sleep(60)  # ждёт 60 секунд
```

При ошибке в `_tick()` планировщик логирует её и продолжает работу (не падает).

---

## Алгоритм тика (`_tick`)

1. `get_due_planned_schedules(session)` — SELECT из `research_schedules` WHERE `status=PLANNED AND scheduled_at <= now()`
2. Для каждого расписания:
   a. Загружает оригинальное исследование (`get_research_by_id`)
   b. `create_scheduled_run(session, schedule, original)` — создаёт дочернее исследование
   c. `run_research.delay(new_research_id, triggered_by="scheduler")` — Celery задача
   d. `reschedule_next(session, schedule)` — помечает текущую запись COMPLETED, создаёт новую PLANNED

---

## Модель `ResearchSchedule`

```
schedule_id      BigInteger PK
research_id      FK → researches  (не уникален — хранится вся история)
scheduled_at     DateTime TZ — время следующего запуска
repeat_type      Text — тип повторения
repeat_value     Integer — числовое значение интервала
repeat_unit      Text — единица: minutes | hours | days | weeks | months | years
status           ENUM: PLANNED | COMPLETED
```

Плюс все поля `ResearchSettingsMixin` (модели и параметры пайплайна).

### `repeat_type`

| Значение | Описание |
|---------|----------|
| `start` | Каждый раз начинает с нуля (без parent_id) |
| `current` | Продолжение текущего исследования (parent_id = оригинальное) |
| `deep` | Углубление цепочки (parent_id = последнее автосозданное исследование) |

### Интервалы

`repeat_value` + `repeat_unit` → `timedelta`. Доступные единицы:
`minutes`, `hours`, `days`, `weeks`, `months` (≈30д), `years` (≈365д).

Следующий запуск: `now() + timedelta(seconds=_UNIT_SECONDS[unit] * value)`.

---

## Auto-reschedule

После каждого успешного запуска `reschedule_next`:
1. Переводит текущую запись в `COMPLETED`
2. Создаёт новую запись `PLANNED` с `scheduled_at = now() + interval`

Таким образом история всех автозапусков сохраняется в `research_schedules`.

---

## Как настроить расписание через UI

1. Открыть страницу исследования → кнопка «Расписание»
2. Выбрать тип повторения (`start` / `current` / `deep`)
3. Указать интервал (например: каждые 7 дней)
4. Настроить модели и параметры пайплайна (опционально)
5. Нажать «Сохранить» → `POST /api/v1/researches/{id}/scheduler`

Для удаления расписания: `DELETE /api/v1/researches/{id}/scheduler`.

---

## CRUD операции

| Функция | Описание |
|---------|----------|
| `upsert_research_schedule(session, research_id, ...)` | Создать или обновить PLANNED запись |
| `get_schedule_by_research_id(session, research_id)` | Получить активное PLANNED расписание |
| `delete_planned_schedule(session, research_id)` | Удалить PLANNED запись |
| `get_due_planned_schedules(session)` | Все просроченные PLANNED записи |
| `create_scheduled_run(session, schedule, original)` | Создать дочернее исследование |
| `reschedule_next(session, schedule)` | Завершить текущее, создать следующее |
