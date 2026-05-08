# Пайплайн исследования

Каждый шаг реализован как класс, наследующий `ResearchStepBase` (`app/core/research/base.py`). Шаги выполняются последовательно внутри `pipeline()` сценария.

---

## Direction (`app/core/research/direction.py`)

**Стадия:** `DIRECTION`

**Что делает:** брейнштормит ключевые векторы исследования через LLM. Если исследование является продолжением (`research_parent_id` задан), сначала суммаризирует сегменты предыдущего исследования с учётом лайков/дизлайков пользователя.

**Входные данные:**
- `research.research_name` — запрос пользователя
- `research.settings_n_vectors` — количество векторов
- `research.research_parent_id` — если задан, загружает контекст предыдущего исследования

**Выходные данные:** текст направления (нумерованный список) → сохраняется в `research.research_direction_content`

**Промпты:** `build_direction_messages` / `build_direction_continuation_messages` / `build_segment_summarize_messages` из `app/services/prompts.py`

**Модель:** `model_id_direction` (обязательна; шаг падает с `DirectionStepError` если не задана)

---

## Keywords (`app/core/research/keywords.py`)

**Стадия:** `KEYWORDS`

**Что делает:** генерирует поисковые запросы для SearXNG на основе темы и направления.

**Входные данные:**
- `research.research_name` — запрос пользователя
- `research.research_direction_content` — результат шага Direction
- `research.settings_n_search_queries` — количество запросов

**Выходные данные:** JSON-массив строк → сохраняется в `research.research_search_keywords`

**Промпт:** `build_search_keywords_messages` (ответ строго в формате JSON-массива)

**Модель:** `model_id_search`

---

## Search (`app/core/research/search.py`)

**Стадия:** `SEARCH`

**Что делает:** поиск страниц через SearXNG, скрейпинг, очистка HTML.

**Входные данные:**
- `research.research_search_keywords` — поисковые запросы
- `research.settings_n_top_search_results` — результатов на запрос
- `research.settings_search_areas` / `settings_exclude_search_areas` — фильтры доменов (`site:domain` / `-site:domain`)
- `research.settings_n_async_parse` — параллельность scraping

**Что происходит внутри:**
1. `_search_top_pages` — SearXNG JSON API, дедупликация URL
2. `_parse_pages` — параллельный scraping через `WebScraper` (curl_cffi, Chrome TLS)
3. `_clean_pages` — извлечение текста через `trafilatura`

**Выходные данные:**
- `research.research_result_search_links` — `[{"url": "..."}]`
- `scrapped_pages` — заполняются `page_raw_content`, `page_clean_content`, `page_scrapped_status`

---

## Chunking (`app/core/research/chunking.py`)

**Стадия:** `SCRAPE`

**Что делает:** разбивает очищенный текст каждой страницы на чанки по количеству токенов и сохраняет в `chunk_summaries`.

**Входные данные:**
- `research.research_result_search_links` — URL для обработки
- `model.model_max_tokens` — максимальный размер чанка (берётся из модели `model_id_embed`)

**Алгоритм:** `tiktoken` (`cl100k_base`) токенизирует текст, нарезает без overlap.

**Выходные данные:** записи в `chunk_summaries` (chunk_id, page_url, research_id, chunk_index, chunk_content). Конфликты обрабатываются через `ON CONFLICT DO UPDATE`.

---

## Scoring Pages

### BM25 (`app/core/research/scoring_pages/bm25.py`)

**Стадия:** `SCORING_BM25`

**Что делает:** TF-IDF ранжирование без LLM.

**Алгоритм:**
1. Строит корпус из всех чанков исследования
2. `BM25Okapi(tokenized_corpus).get_scores(query_tokens)` — query = `research_name + direction`
3. Нормализует скоры к `[0, 1]`
4. Сохраняет `bm25_score` в `ChunkSummary`
5. Топ-N (`settings_n_top_bm25_chunks`) → `research.research_result_bm25_chunks`

**Зависимости:** `rank_bm25`

---

### Embed (`app/core/research/scoring_pages/embed.py`)

**Стадия:** `SCORING_EMBED`

**Условие запуска:** есть `model_id_embed` и есть bm25-чанки.

**Что делает:** косинусное сходство между эмбеддингом запроса и эмбеддингом каждого чанка.

**Алгоритм:**
1. Создаёт эмбеддинг `query + direction` (кэш в `research.research_result_embed_summary`)
2. Для каждого bm25-чанка: эмбеддинг контента (кэш в `ChunkSummary.page_embed`)
3. Косинусное сходство → `ChunkSummary.embed_score`
4. Топ-N → `research.research_result_embed_chunks`

**Модель:** `model_id_embed` (LLMClient.embed)

---

### Rerank (`app/core/research/scoring_pages/rerank.py`)

**Стадия:** `SCORING_RERANK`

**Условие запуска:** есть `model_id_reranker` и есть embed-чанки.

**Что делает:** LLM оценивает релевантность каждого чанка к запросу, возвращая `score: float ∈ [0..1]`.

**Алгоритм:**
1. Для каждого embed-чанка: `llm.generate_structured(context, output_type=_RerankScore)`
2. Кэш: если `ChunkSummary.rerank_score` уже есть — пропускает
3. `ChunkSummary.rerank_score = score`
4. Топ-N → `research.research_result_rerank_chunks`

**Модель:** `model_id_reranker` (pydantic-ai structured output)

---

## Summarize (`app/core/research/summarize.py`)

**Стадия:** `SUMMARIZE`

**Что делает:** генерирует bullet-point суммари для каждого чанка через LLM.

**Выбор чанков:** `rerank_chunks → embed_chunks[:n] → bm25_chunks[:n]` (лучший доступный набор).

**Кэш:** если `ChunkSummary.page_summary` уже заполнен — пропускает чанк.

**Выходные данные:** `ChunkSummary.page_summary` для каждого чанка.

**Модель:** `model_id_answer`

---

## Write (`app/core/research/write/`)

**Стадия:** `WRITE`

### StandardWriteStep (`standard.py`)
Используется для обоих сценариев (Normal и Question), отличается только промптом:
- **Normal**: `build_write_normal_messages` — развёрнутый текст с разделами `##`, цитаты `[N]`
- **Question**: `build_write_question_messages` — ответ 1–3 абзаца, цитаты `[N]`

**Алгоритм:**
1. Берёт чанки из `research_result_rerank_chunks` с их `page_summary`
2. Формирует нумерованный список источников (дедупликация по URL)
3. Один LLM-вызов → Markdown-текст
4. `apply_citations(text, url_map)` — заменяет `[N]` на `[[N]](url)`
5. `format_as_segments(text)` — конвертирует Markdown в типизированные сегменты

### Утилиты (`segments.py`)
- `format_as_segments(text)` — парсит Markdown по строкам, создаёт сегменты типов `h1..h6`, `p`, `li`; каждый сегмент: `{type, content (HTML), is_like: false, is_dislike: false, comment: null}`
- `apply_citations(text, url_map)` — заменяет `[N]` → `[[N]](url)`
- `_apply_markdown_links(text)` — Markdown-ссылки `[text](url)` → HTML `<a>`
- `_apply_inline_markdown(text)` — `**bold**` → `<b>`, `*italic*` → `<i>`

---

## Rename (`app/core/research/rename.py`)

**Стадия:** `RENAME`

**Что делает:** генерирует короткое название исследования (4–6 слов, ≤100 символов) через LLM.

**Условия пропуска:**
- `research_body_finish` пуст
- Пользователь уже переименовал исследование (`research.research_name != original query`)

**Алгоритм:**
1. Берёт заголовок h1 из первого сегмента `research_body_finish`
2. `build_rename_messages(h1, query)` → LLM → короткое название
3. Обновляет `research.research_name`

**Модель:** `model_id_answer`
