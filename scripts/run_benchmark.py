"""Run benchmark cases through one DeepResearch system and save iterative results.

Reads cases from `data/input-cases.json`, runs the selected system on each prompt,
asks an LLM-judge to verdict every cited source, and appends one JSONL line per
completed case to the output file. Output schema is described in
`new-metrics.md` (раздел 1.7).

Usage:
    python scripts/run_benchmark.py                                    # openai_dr by default
    python scripts/run_benchmark.py --system wide_researcher
    python scripts/run_benchmark.py --system oss_dr --slice 0:5
    python scripts/run_benchmark.py --input data/input-cases.json --output data/foo.jsonl
    python scripts/run_benchmark.py --mock                              # no real API calls
    python scripts/run_benchmark.py --no-resume                         # do not skip done cases
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

DEFAULT_INPUT = Path("data/input-cases.json")
SYSTEM_CHOICES = ("openai_dr", "wide_researcher", "oss_dr")


def _load_env_file() -> None:
    """Load KEY=VALUE pairs from `.env` into `os.environ` without overriding existing values.

    Looks at cwd first, then project root (one level above `scripts/`).
    """
    for path in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)
        return


_load_env_file()


@dataclass
class JudgeVerdict:
    url: str
    verdict: str  # "Yes" | "No" | "Error" — "Error" = страницу/LLM не удалось дотянуть до вердикта
    reasoning: str = ""


@dataclass
class SystemRun:
    status: str  # "ok" | "error"
    error: str | None = None
    answer_text: str = ""
    sources: list[str] = field(default_factory=list)
    gen_time_sec: float = 0.0
    cost_usd: float = 0.0
    judge_verdicts: list[JudgeVerdict] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class SystemRunner(Protocol):
    name: str

    async def run(self, prompt: str) -> tuple[str, list[str], float, float]:
        """Run one query.

        Returns:
            (answer_text, sources, gen_time_sec, cost_usd)
        """
        ...


class OpenAIDRRunner:
    """OpenAI Deep Research runner via the Responses API.

    Required env vars (положи в `.env`):
        OPENAI_API_KEY        — API-ключ OpenAI

    Optional env vars:
        OPENAI_DR_MODEL       — модель (default: gpt-5-nano — самая слабая DR-модель)
        OPENAI_DR_INPUT_RATE  — стоимость в USD за 1M input-токенов (default: 0.05)
        OPENAI_DR_OUTPUT_RATE — стоимость в USD за 1M output-токенов (default: 0.40)
        OPENAI_DR_TIMEOUT     — timeout HTTP-клиента, секунды (default: 1800)
    """

    name = "openai_dr"

    def __init__(self) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise RuntimeError("openai package is not installed. Run: poetry install") from e

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env or export the variable.")

        timeout = float(os.environ.get("OPENAI_DR_TIMEOUT", "1800"))
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._model = os.environ.get("OPENAI_DR_MODEL", "gpt-5-nano")
        self._input_rate = float(os.environ.get("OPENAI_DR_INPUT_RATE", "0.05"))
        self._output_rate = float(os.environ.get("OPENAI_DR_OUTPUT_RATE", "0.40"))

    async def run(self, prompt: str) -> tuple[str, list[str], float, float]:
        t0 = time.perf_counter()
        response = await self._client.responses.create(
            model=self._model,
            input=prompt,
            tools=[{"type": "web_search_preview"}],
            reasoning={"summary": "auto"},
        )
        gen_time = time.perf_counter() - t0

        answer_text = getattr(response, "output_text", "") or ""

        sources: list[str] = []
        seen: set[str] = set()
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "message":
                continue
            for content in getattr(item, "content", []) or []:
                for ann in getattr(content, "annotations", []) or []:
                    if getattr(ann, "type", None) == "url_citation":
                        url = getattr(ann, "url", None)
                        if url and url not in seen:
                            seen.add(url)
                            sources.append(url)

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
        cost = input_tokens / 1_000_000 * self._input_rate + output_tokens / 1_000_000 * self._output_rate
        return answer_text, sources, gen_time, cost


class WideResearcherRunner:
    """WideResearcher runner.

    Бьёт `POST {WIDE_RESEARCHER_URL}/api/v1/researches/run-sync` с авторизацией
    через cookie `access_token={WIDE_RESEARCHER_TOKEN}`. Сервер запускает
    Celery-задачу, ждёт её завершения и отдаёт JSON с answer_text + sources.

    Required env vars (положи в `.env`):
        WIDE_RESEARCHER_URL    — base URL запущенного инстанса (например, http://localhost:6720)
        WIDE_RESEARCHER_TOKEN  — JWT из cookie `access_token` авторизованного пользователя

    Optional env vars:
        WIDE_RESEARCHER_TIMEOUT       — таймаут HTTP-клиента в секундах (default: 1800)
        WIDE_RESEARCHER_POLL_INTERVAL — период опроса БД на сервере, секунды (default: 5.0)
    """

    name = "wide_researcher"

    def __init__(self) -> None:
        try:
            import aiohttp  # noqa: F401  (импорт проверяет наличие пакета)
        except ImportError as e:
            raise RuntimeError("aiohttp package is not installed. Run: poetry install") from e

        url = os.environ.get("WIDE_RESEARCHER_URL")
        token = os.environ.get("WIDE_RESEARCHER_TOKEN")
        if not url:
            raise RuntimeError("WIDE_RESEARCHER_URL is not set. Add it to .env or export the variable.")
        if not token:
            raise RuntimeError("WIDE_RESEARCHER_TOKEN is not set. Add it to .env or export the variable.")

        self._base_url = url.rstrip("/")
        self._token = token
        self._timeout = float(os.environ.get("WIDE_RESEARCHER_TIMEOUT", "1800"))
        self._poll_interval = float(os.environ.get("WIDE_RESEARCHER_POLL_INTERVAL", "5.0"))

    async def run(self, prompt: str) -> tuple[str, list[str], float, float]:
        import aiohttp

        endpoint = f"{self._base_url}/api/v1/researches/run-sync"
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        cookies = {"access_token": self._token}
        data = {
            "prompt": prompt,
            "timeout_seconds": str(int(self._timeout)),
            "poll_interval_seconds": str(self._poll_interval),
        }

        t0 = time.perf_counter()
        async with aiohttp.ClientSession(cookies=cookies, timeout=timeout) as http:
            async with http.post(endpoint, data=data) as response:
                payload: dict[str, Any] = await response.json()
                status_code = response.status
        gen_time = time.perf_counter() - t0

        if status_code >= 400:
            raise RuntimeError(f"WideResearcher HTTP {status_code}: {payload}")

        status = payload.get("status")
        if status != "complete":
            raise RuntimeError(f"WideResearcher status={status!r}: {payload.get('error') or payload}")

        answer = payload.get("answer_text") or ""
        sources = payload.get("sources") or []
        # WideResearcher self-hosted — прямых API-расходов на запрос нет.
        return answer, list(sources), gen_time, 0.0


class OSSDRRunner:
    """OSS Deep Researcher runner (популярный open-source аналог на той же Qwen 3.5 9B).

    Required env vars (положи в `.env`):
        OSS_DR_URL    — endpoint выбранного OSS DeepResearcher
        OSS_DR_TOKEN  — API-токен / ключ доступа (если требуется)
    """

    name = "oss_dr"

    async def run(self, prompt: str) -> tuple[str, list[str], float, float]:
        raise NotImplementedError(
            "OSS Deep Researcher runner is not implemented yet. "
            "Fill in subprocess or HTTP call configured via OSS_DR_URL."
        )


class MockRunner:
    """Deterministic mock runner for pipeline-only testing."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, prompt: str) -> tuple[str, list[str], float, float]:
        rng = random.Random(hash((prompt, self.name)))
        n_sources = rng.randint(3, 10)
        sources = [f"https://example-{self.name}.com/article-{rng.randint(1000, 9999)}" for _ in range(n_sources)]
        gen_time = rng.uniform(20.0, 120.0)
        cost = 0.0 if self.name in ("wide_researcher", "oss_dr") else rng.uniform(0.1, 1.5)
        await asyncio.sleep(0.02)
        return f"[mock answer for {prompt[:60]}...]", sources, gen_time, cost


class Judge(Protocol):
    async def verdict(self, prompt: str, source_url: str, answer_snippet: str) -> JudgeVerdict: ...


_JUDGE_TOKEN_ENCODING = "cl100k_base"


class LLMJudge:
    """LLM-as-a-Judge через OpenAI-совместимый API.

    Алгоритм для одного URL:
        1. Скачивает HTML (`aiohttp`).
        2. Чистит до основного текста через `trafilatura.extract` (та же
           библиотека, что и в проде, см. `app/services/page_cleaner.py`).
        3. Режет текст на чанки по `JUDGE_CHUNK_TOKENS` токенов с помощью
           `tiktoken` (кодировка `cl100k_base`, как в `app/core/research/chunking.py`).
        4. Последовательно спрашивает модель по каждому чанку — поддерживает ли
           он хоть одно фактическое утверждение из ответа. Возвращает "Yes" на
           первом подтверждающем чанке (короткое замыкание); если все ответили
           "No" — итоговый вердикт "No".

    Required env vars (положи в `.env`):
        JUDGE_API_KEY        — API-ключ судейской LLM

    Optional env vars:
        JUDGE_BASE_URL       — base URL OpenAI-совместимого API
                               (напр. https://openrouter.ai/api/v1, http://localhost:8000/v1).
                               По умолчанию — официальный OpenAI.
        JUDGE_MODEL          — имя модели (default: gpt-4o-mini)
        JUDGE_TIMEOUT        — таймаут одного LLM-вызова, сек (default: 120)
        JUDGE_FETCH_TIMEOUT  — таймаут загрузки страницы, сек (default: 30)
        JUDGE_CHUNK_TOKENS   — размер чанка контента в токенах (default: 8000)
        JUDGE_TEMPERATURE    — температура; если не задана, параметр не передаётся
                               (нужно для reasoning-моделей вроде gpt-5/o1, которые
                               принимают только дефолтное значение).
    """

    _SYSTEM_PROMPT = (
        "You are a strict fact-checking judge. "
        "Given a user query, a generated answer, a source URL and ONE chunk of the source page, "
        "decide whether THIS chunk genuinely supports at least one factual claim from the answer "
        "that is relevant to the query. "
        "If the chunk is unrelated, paywalled, empty, a 404, or contradicts the answer — say No. "
        'Reply with a single JSON object: {"verdict": "Yes" | "No", "reasoning": "<one short sentence>"}. '
        "Output JSON only, no prose, no markdown fences."
    )

    def __init__(self) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise RuntimeError("openai package is not installed. Run: poetry install") from e
        try:
            import aiohttp  # noqa: F401
        except ImportError as e:
            raise RuntimeError("aiohttp package is not installed. Run: poetry install") from e
        try:
            import trafilatura  # noqa: F401
        except ImportError as e:
            raise RuntimeError("trafilatura package is not installed. Run: poetry install") from e
        try:
            import tiktoken
        except ImportError as e:
            raise RuntimeError("tiktoken package is not installed. Run: poetry install") from e

        api_key = os.environ.get("JUDGE_API_KEY")
        if not api_key:
            raise RuntimeError("JUDGE_API_KEY is not set. Add it to .env or export the variable.")

        base_url = os.environ.get("JUDGE_BASE_URL") or None
        timeout = float(os.environ.get("JUDGE_TIMEOUT", "120"))
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._model = os.environ.get("JUDGE_MODEL", "gpt-4o-mini")
        self._fetch_timeout = float(os.environ.get("JUDGE_FETCH_TIMEOUT", "30"))
        self._chunk_tokens = max(int(os.environ.get("JUDGE_CHUNK_TOKENS", "8000")), 1)
        temp_raw = os.environ.get("JUDGE_TEMPERATURE")
        # None → не передавать параметр в API (reasoning-модели типа gpt-5/o1
        # принимают только дефолтную температуру и валятся на любых других).
        self._temperature: float | None = float(temp_raw) if temp_raw not in (None, "") else None
        self._encoding = tiktoken.get_encoding(_JUDGE_TOKEN_ENCODING)

    async def verdict(self, prompt: str, source_url: str, answer_snippet: str) -> JudgeVerdict:
        try:
            page_text = await self._fetch_and_clean(source_url)
        except Exception as e:
            return JudgeVerdict(url=source_url, verdict="Error", reasoning=f"fetch error: {type(e).__name__}: {e}")

        if not page_text:
            return JudgeVerdict(url=source_url, verdict="Error", reasoning="empty or unreadable page")

        chunks = self._chunk_by_tokens(page_text)
        if not chunks:
            return JudgeVerdict(url=source_url, verdict="Error", reasoning="no content after tokenisation")

        last_reasoning = "no chunk supports the answer"
        had_real_judgment = False
        for idx, chunk in enumerate(chunks):
            try:
                v, reasoning = await self._judge_chunk(prompt, answer_snippet, source_url, chunk, idx, len(chunks))
            except Exception as e:
                last_reasoning = f"chunk {idx + 1}/{len(chunks)}: llm error: {type(e).__name__}: {e}"
                continue
            had_real_judgment = True
            if v == "Yes":
                return JudgeVerdict(
                    url=source_url,
                    verdict="Yes",
                    reasoning=f"chunk {idx + 1}/{len(chunks)}: {reasoning}"[:500],
                )
            last_reasoning = f"chunk {idx + 1}/{len(chunks)}: {reasoning}"
        # Если ни один чанк не дал реального вердикта (все упали с LLM-ошибкой) —
        # помечаем как недостижимый, чтобы не портил validity_rate.
        verdict_value = "No" if had_real_judgment else "Error"
        return JudgeVerdict(url=source_url, verdict=verdict_value, reasoning=last_reasoning[:500])

    async def _judge_chunk(
        self,
        prompt: str,
        answer_snippet: str,
        source_url: str,
        chunk: str,
        chunk_idx: int,
        chunks_total: int,
    ) -> tuple[str, str]:
        user_content = (
            f"User query:\n{prompt}\n\n"
            f"Generated answer (may be truncated):\n{answer_snippet[:4000]}\n\n"
            f"Source URL: {source_url}\n"
            f"Source page chunk {chunk_idx + 1} of {chunks_total} (cleaned plain text):\n{chunk}\n\n"
            'Reply with JSON only: {"verdict": "Yes" | "No", "reasoning": "<one short sentence>"}'
        )
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        response = await self._client.chat.completions.create(**kwargs)
        content = (response.choices[0].message.content or "").strip()
        return self._parse_verdict(content)

    def _chunk_by_tokens(self, text: str) -> list[str]:
        """Режет plain-text на чанки ровно по `self._chunk_tokens` токенов tiktoken."""
        tokens = self._encoding.encode(text)
        if not tokens:
            return []
        out: list[str] = []
        for i in range(0, len(tokens), self._chunk_tokens):
            out.append(self._encoding.decode(tokens[i : i + self._chunk_tokens]))
        return out

    async def _fetch_and_clean(self, url: str) -> str:
        """Скачивает HTML и извлекает основной текст через `trafilatura.extract`."""
        import aiohttp
        import trafilatura

        timeout = aiohttp.ClientTimeout(total=self._fetch_timeout)
        headers = {"User-Agent": "Mozilla/5.0 (compatible; WideResearcherBenchmarkJudge/1.0)"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as http:
            async with http.get(url, allow_redirects=True) as response:
                response.raise_for_status()
                raw = await response.text(errors="replace")

        # trafilatura.extract — синхронный CPU-bound вызов (lxml внутри); уводим в поток,
        # чтобы не блокировать event loop.
        extracted = await asyncio.to_thread(
            trafilatura.extract,
            raw,
            include_formatting=False,
            no_fallback=False,
        )
        return (extracted or "").strip()

    @staticmethod
    def _parse_verdict(content: str) -> tuple[str, str]:
        """Парсит ответ модели в (verdict, reasoning). Терпим к шуму вокруг JSON."""
        m = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
                v_raw = str(parsed.get("verdict", "")).strip().lower()
                reasoning = str(parsed.get("reasoning", "") or "").strip()
                if v_raw.startswith("y"):
                    return "Yes", reasoning or "supported"
                if v_raw.startswith("n"):
                    return "No", reasoning or "not supported"
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass
        # Fallback: ищем явное Yes/No в свободном тексте.
        low = content.lower()
        if re.search(r"\byes\b", low) and not re.search(r"\bno\b", low):
            return "Yes", content[:200]
        return "No", content[:200] or "unparseable judge response"


class MockJudge:
    async def verdict(self, prompt: str, source_url: str, answer_snippet: str) -> JudgeVerdict:
        rng = random.Random(hash((prompt, source_url)))
        v = "Yes" if rng.random() > 0.25 else "No"
        return JudgeVerdict(url=source_url, verdict=v, reasoning=f"[mock: {v}]")


def compute_metrics(run: SystemRun) -> dict[str, Any]:
    n_sources = len(run.sources)
    n_valid = sum(1 for v in run.judge_verdicts if v.verdict == "Yes")
    n_invalid = sum(1 for v in run.judge_verdicts if v.verdict == "No")
    n_unreachable = sum(1 for v in run.judge_verdicts if v.verdict == "Error")
    n_evaluable = n_valid + n_invalid
    unique_domains = len({urlparse(u).netloc for u in run.sources if u})
    return {
        "n_sources": n_sources,
        "n_valid": n_valid,
        "n_invalid": n_invalid,
        "n_unreachable": n_unreachable,  # страницы, которые не получилось дотянуть до вердикта
        "n_evaluable": n_evaluable,  # n_sources - n_unreachable
        # validity_rate — пессимистичный: ошибки сетки/LLM считаются как "невалид".
        "validity_rate": (n_valid / n_sources) if n_sources else 0.0,
        # validity_rate_evaluable — честный: считаем долю только среди реально проверенных.
        "validity_rate_evaluable": (n_valid / n_evaluable) if n_evaluable else None,
        "unique_domains": unique_domains,
        "time_per_valid": (run.gen_time_sec / n_valid) if n_valid else None,
        "cost_per_valid": (run.cost_usd / n_valid) if n_valid else None,
    }


async def run_one_system(runner: SystemRunner, prompt: str, judge: Judge) -> dict[str, Any]:
    try:
        answer, sources, gen_time, cost = await runner.run(prompt)
    except Exception as e:
        return asdict(SystemRun(status="error", error=f"{type(e).__name__}: {e}"))

    run = SystemRun(
        status="ok",
        answer_text=answer,
        sources=sources,
        gen_time_sec=gen_time,
        cost_usd=cost,
    )

    verdict_results = await asyncio.gather(
        *(judge.verdict(prompt, s, answer) for s in sources),
        return_exceptions=True,
    )
    for src, v in zip(sources, verdict_results, strict=True):
        if isinstance(v, Exception):
            run.judge_verdicts.append(JudgeVerdict(url=src, verdict="Error", reasoning=f"judge error: {v}"))
        else:
            run.judge_verdicts.append(v)

    run.metrics = compute_metrics(run)
    return asdict(run)


async def run_one_case(case: dict[str, Any], runner: SystemRunner, judge: Judge) -> dict[str, Any]:
    started_at = datetime.now(UTC).isoformat()
    system_result = await run_one_system(runner, case["prompt"], judge)
    return {
        "case_id": case["id"],
        "category_code": case["category_code"],
        "category": case["category"],
        "prompt": case["prompt"],
        "freshness": case["freshness"],
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "systems": {runner.name: system_result},
    }


def load_completed_case_ids(output_path: Path, system_name: str) -> set[str]:
    """Возвращает case_id, для которых в output уже есть УСПЕШНЫЙ запуск выбранной системы.

    Кейсы с `status == "error"` намеренно не скипаются — их нужно перепрогнать.
    """
    if not output_path.exists():
        return set()
    done: set[str] = set()
    with output_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                system_result = record.get("systems", {}).get(system_name)
                if system_result and system_result.get("status") == "ok":
                    done.add(record["case_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def purge_error_records(output_path: Path, system_name: str) -> int:
    """Удаляет из output JSONL записи, в которых выбранная система имеет `status == "error"`.

    Перезаписывает файл атомарно (через temp + rename). Если файла нет — возвращает 0.
    Возвращает количество удалённых записей.
    """
    if not output_path.exists():
        return 0
    kept: list[str] = []
    removed = 0
    with output_path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                kept.append(stripped)
                continue
            system_result = record.get("systems", {}).get(system_name)
            if system_result and system_result.get("status") == "error":
                removed += 1
                continue
            kept.append(json.dumps(record, ensure_ascii=False))
    if removed:
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            for entry in kept:
                f.write(entry + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(output_path)
    return removed


def parse_slice(s: str) -> slice:
    if ":" in s:
        a, b = s.split(":", 1)
        return slice(int(a) if a else None, int(b) if b else None)
    return slice(0, int(s))


def build_runner(system: str, mock: bool) -> SystemRunner:
    if mock:
        return MockRunner(system)
    return {
        "openai_dr": OpenAIDRRunner,
        "wide_researcher": WideResearcherRunner,
        "oss_dr": OSSDRRunner,
    }[system]()


def build_judge(mock: bool) -> Judge:
    return MockJudge() if mock else LLMJudge()


def default_output_for(system: str) -> Path:
    return Path(f"data/results-{system.replace('_', '-')}.jsonl")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark cases through one selected DeepResearch system.")
    parser.add_argument(
        "--system",
        type=str,
        choices=SYSTEM_CHOICES,
        default="openai_dr",
        help="Which DeepResearch system to run (default: openai_dr).",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input JSON (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSONL (default: data/results-{system}.jsonl).",
    )
    parser.add_argument(
        "--slice",
        type=str,
        default=":",
        help="Python-style slice on cases (e.g. '0:5', '10:', '5'). Default: all.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock runner and judge (for pipeline testing).",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Process all cases in slice, even if already present in output.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="How many cases to run through the runner in parallel (default: 1, sequential).",
    )
    args = parser.parse_args()

    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")

    if args.output is None:
        args.output = default_output_for(args.system)

    data = json.loads(args.input.read_text(encoding="utf-8"))
    all_cases = data["cases"]
    sliced_cases = all_cases[parse_slice(args.slice)]
    print(f"Loaded {len(sliced_cases)}/{len(all_cases)} cases from {args.input} (slice={args.slice})")

    try:
        runner = build_runner(args.system, args.mock)
    except Exception as e:
        print(f"Failed to init runner '{args.system}': {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
    judge = build_judge(args.mock)
    print(
        f"System: {runner.name} ({type(runner).__name__}) | "
        f"judge: {type(judge).__name__} | mock={args.mock} | concurrency={args.concurrency}"
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)

    iteration = 0
    while True:
        iteration += 1
        print(f"\n=== Iteration {iteration} ===")

        if not args.no_resume:
            removed = purge_error_records(args.output, args.system)
            if removed:
                print(f"Purged {removed} error records from {args.output} — they will be retried.")

        done = set() if args.no_resume else load_completed_case_ids(args.output, args.system)
        if done:
            print(f"Skipping {len(done)} successful cases already in {args.output}")
        cases = [c for c in sliced_cases if c["id"] not in done]
        if not cases:
            print("Nothing to do — all cases completed successfully.")
            break

        successful = await _run_cases(args, cases, runner, judge)
        print(f"Iteration {iteration}: {successful}/{len(cases)} succeeded.")

        if args.no_resume:
            # --no-resume отключает skipping, иначе следующая итерация снова прогонит всё.
            break
        if successful == 0:
            print(
                f"Iteration {iteration} produced 0 successful runs out of {len(cases)}. "
                "Stopping to avoid an infinite retry loop."
            )
            break

    print(f"\nFinished. Output: {args.output}")


async def _run_cases(
    args: argparse.Namespace,
    cases: list[dict[str, Any]],
    runner: SystemRunner,
    judge: Judge,
) -> int:
    """Прогоняет cases через runner+judge, дописывая результат в args.output.

    Возвращает количество кейсов, завершившихся с `status == "ok"`.
    """
    sem = asyncio.Semaphore(args.concurrency)
    file_lock = asyncio.Lock()
    total = len(cases)
    completed = 0
    successful = 0

    with args.output.open("a", encoding="utf-8") as f:

        async def process(idx: int, case: dict[str, Any]) -> None:
            nonlocal completed, successful
            async with sem:
                t0 = time.perf_counter()
                print(f"[{idx}/{total}] {case['id']} starting...", flush=True)
                try:
                    rec = await run_one_case(case, runner, judge)
                except Exception as e:
                    print(f"[{idx}/{total}] {case['id']} FAILED: {type(e).__name__}: {e}", file=sys.stderr)
                    return
                elapsed = time.perf_counter() - t0
            async with file_lock:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
                completed += 1
                system_result = rec["systems"][runner.name]
                if system_result.get("status") == "ok":
                    successful += 1
                metrics = system_result.get("metrics", {})
                print(
                    f"[{completed}/{total}] {case['id']} done in {elapsed:.1f}s | "
                    f"n_valid={metrics.get('n_valid', 'ERR')} / "
                    f"n_sources={metrics.get('n_sources', 'ERR')} "
                    f"(unreachable={metrics.get('n_unreachable', 'ERR')})"
                )

        await asyncio.gather(*(process(i, c) for i, c in enumerate(cases, 1)))

    return successful


if __name__ == "__main__":
    asyncio.run(main())
