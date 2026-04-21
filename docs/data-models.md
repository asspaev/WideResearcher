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
model_type       Text  ("api" | "vllm")
model_name       String(120)
model_api_type   Text  (опционально, для api)
model_path       Text  (опционально, для vllm)
model_key_api    Text  (опционально)
model_key_answer Text  (опционально)
→ outputs (ModelOutput)
```

## Research (`researches`) — центральная сущность
```
research_id              BigInteger PK
user_id                  FK → users
research_parent_id       FK → researches (наследование, опционально)
research_status          ENUM: IN_PROCESS | COMPLETE | ERROR
research_name            Text
research_version_name    Text
research_body            JSONB (результат)
settings_search_areas    JSONB
settings_exclude_search_areas JSONB
settings_epochs_count    Integer (default=5)
model_id_answer          BigInteger FK → models
model_id_search          BigInteger FK → models
model_id_direction       BigInteger FK → models (опционально)
→ epochs (ResearchEpoch), schedules (ResearchSchedule), outputs (ModelOutput)
```

## ResearchEpoch (`research_epochs`) — одна итерация
```
research_id                  FK → researches  (PK составной)
epoch_id                     Integer          (PK составной)
research_body_start          JSONB
research_body_finish         JSONB
research_direction_content   Text (опционально)
research_search_keywords     JSONB (опционально)
research_result_search_links JSONB (опционально)
```

## ResearchSchedule (`research_schedules`) — планировщик
```
schedule_id      BigInteger PK
research_id      FK → researches
scheduled_at     DateTime with TZ
repeat_interval  Interval (опционально)
status           ENUM: PLANNED | COMPLETED
```

## ModelOutput (`model_outputs`) — трекинг LLM-вызовов
```
response_id      BigInteger PK
model_id         FK → models
research_id      FK → researches
epoch_id         Integer
response_status  ENUM: PROCESSING | COMPLETE | ERROR
step_type        Text
model_input      JSONB
model_output     JSONB
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
ModelCard(ModelBase): model_created_time (str), model_used_count (int)

# app/schemas/research.py
ResearchBase: research_id, research_name
ResearchCard(ResearchBase): research_version_name, research_last_update_time, schedule_next_launch_time
NearestResearch(ResearchBase): schedule_next_launch_time
```

Все схемы с `model_config = ConfigDict(from_attributes=True)`.

### Счётчик использования моделей
`ModelOutput` связывает модель с конкретным вызовом. `model_used_count` в `ModelCard` = `count_model_outputs_by_model_id(session, model_id)` из `app/crud/model_output.py`.

### JSONB поля
`Research.research_body`, `settings_*`, `ResearchEpoch.*` — JSONB в PostgreSQL. SQLAlchemy 2.0+ сериализует автоматически, дополнительных преобразований не нужно.
