# Сервисы

## LLMClient (`app/services/llm_client.py`)

Async-клиент для обращения к OpenAI-совместимым API. Работает с любым провайдером: OpenAI, vLLM, Ollama, LM Studio и др.

### Создание клиента
```python
client = LLMClient(
    model_name="gpt-4o",
    base_url="https://api.openai.com/v1",
    api_key="sk-...",  # None для локальных серверов
)
```

### Методы

**`generate(context, session, model_id, research_id, step_type) → str`**
Отправляет сообщения в Chat Completions API, возвращает текст ответа.

**`embed(text, session, model_id, research_id, step_type) → list[float]`**
Возвращает вектор эмбеддинга через Embeddings API.

**`generate_structured(context, output_type, session, model_id, research_id, step_type) → T`**
Возвращает структурированный ответ в виде Pydantic-модели (через `pydantic-ai`).

### Отслеживание вызовов
Каждый вызов автоматически:
1. Создаёт запись `ModelOutput` со статусом `PROCESSING`
2. После получения ответа обновляет до `COMPLETE` (или `ERROR`)
3. Сохраняет `model_input` и `model_output` в JSONB

Это позволяет отслеживать все LLM-вызовы в разрезе шагов пайплайна.

---

## SearXNG Client (`app/services/searxng_client.py`)

HTTP-клиент для SearXNG JSON API.

```python
client = SearXNGClient(base_url="http://localhost:8080")
results = await client.search("quantum computing 2024", n_results=10)
# results: list[SearchResult(title, url, description)]
```

**Настройка:** URL задаётся через переменную окружения → `get_settings().searxng.url`.

**Возвращаемый формат:** список `SearchResult(title: str, url: str, description: str)`.

---

## Web Scraper (`app/services/web_scraper.py`)

Загружает сырой HTML с веб-страниц.

```python
scraper = WebScraper()
html = await scraper.fetch("https://example.com")  # str | None
```

**Зачем curl_cffi:** `httpx` не имитирует TLS-отпечаток браузера — сайты с Cloudflare/anti-bot защитой блокируют запросы. `curl_cffi` использует `impersonate="chrome"`, имитируя Chrome.

**Параметры:**
- Таймаут: 15 секунд на запрос
- Retry: 3 попытки с задержкой 1 секунда между ними
- User-Agent: случайный реальный браузер через `fake-useragent`

Возвращает `None` если все попытки провалились (страница пропускается без ошибки пайплайна).

---

## Page Cleaner

Очистка HTML происходит внутри `SearchResearchStep._clean_pages()` через **trafilatura**:
```python
trafilatura.extract(html, include_formatting=False, no_fallback=False)
```

Trafilatura удаляет: навигацию, хедер, футер, сайдбары, рекламу, скрипты, стили. Оставляет: основной текстовый контент статьи/страницы.

Результат сохраняется в `ScrappedPage.page_clean_content` со статусом `SUCCESS`.

---

## Data Fetch (`app/services/data_fetch.py`)

Функции для подготовки данных к рендерингу UI.

**`get_models_cards(user_cookie, session) → list[ModelCard]`**
Список моделей пользователя с количеством использований (`model_used_count`).

**`get_researches_cards(user_cookie, session) → list[dict]`**
Список исследований со временем последнего обновления и следующего запуска.

**`get_research_detail(research, session) → dict`**
Детальные данные для страницы исследования: сегменты, расписание, названия моделей, родительская версия.

**`get_research_settings(user_id, session, cache) → dict`**
Настройки из Redis-кэша; при отсутствии возвращает дефолты (первая доступная модель пользователя).

**Redis-ключи:**
- `research_settings:{user_id}` — настройки нового исследования
- `research_step_settings:{user_id}:{research_id}` — настройки следующего шага
- `scheduler_settings:{user_id}:{research_id}` — настройки для планировщика

---

## Prompts (`app/services/prompts.py`)

Все шаблоны промптов и функции их сборки.

| Функция | Назначение | Шаг |
|---------|-----------|-----|
| `build_direction_messages(query, n_vectors)` | Брейншторм векторов | DIRECTION |
| `build_direction_continuation_messages(query, n_vectors, prev_context)` | Направление при продолжении | DIRECTION |
| `build_segment_summarize_messages(segment_text, query)` | Суммари сегмента предыдущего исследования | DIRECTION |
| `build_search_keywords_messages(query, direction, n_keywords)` | Поисковые запросы | KEYWORDS |
| `build_write_normal_messages(query, direction, summaries)` | Написание аналитической статьи | WRITE (Normal) |
| `build_write_question_messages(query, summaries)` | Краткий ответ на вопрос | WRITE (Question) |
| `build_rename_messages(h1, query)` | Генерация короткого названия | RENAME |
| `build_plan_structure_messages(query, direction, summaries)` | Планирование структуры | STRUCTURE (не используется в текущих сценариях) |
| `build_write_chapter_messages(query, direction, summaries, structure, chapter, written_so_far)` | Написание по главам | WRITE (не используется в текущих сценариях) |

### Как добавить новый промпт
1. Добавить константы `MY_SYSTEM` и `MY_USER` в `prompts.py`
2. Написать функцию `build_my_messages(...) → list[dict]`
3. Использовать через `llm.generate(messages, ...)`
