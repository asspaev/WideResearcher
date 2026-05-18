"""Run short-fact QA benchmark cases through one DeepResearch system.

Reads cases from `data/input-qa-cases.json` (30 коротких фактологических
вопросов с одним каноническим ответом каждый), прогоняет выбранную
систему по каждому промпту и спрашивает LLM-судью, совпадает ли
финальный ответ системы с эталоном. На выходе — JSONL-файл вида
`data/results-qa-{system}.jsonl`, одна строка на завершённый кейс.

Этот бенчмарк намеренно отличается от `run_benchmark.py`:
    - оценивается **только корректность финального ответа**, без
      посудержания каждой ссылки;
    - вердикт судьи — один на кейс (`correct ∈ {Yes, No, Error}`);
    - sources всё равно сохраняются (для последующей качественной
      аналитики), но не идут в метрики качества.

Систему-раннер берём из `scripts/run_benchmark.py` без копирования —
импортируем готовые классы.

Usage:
    python scripts/run_qa_benchmark.py                                 # openai_dr by default
    python scripts/run_qa_benchmark.py --system wide_researcher
    python scripts/run_qa_benchmark.py --system oss_dr --slice 0:5
    python scripts/run_qa_benchmark.py --mock                          # no real API calls
    python scripts/run_qa_benchmark.py --no-resume                     # do not skip done cases
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
import traceback
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Готовые раннеры систем и утилиты — из соседнего скрипта в той же папке.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_benchmark import SYSTEM_CHOICES, SystemRunner, build_runner, parse_slice  # noqa: E402

DEFAULT_INPUT = Path("data/input-qa-cases.json")


@dataclass
class QAVerdict:
    correct: str  # "Yes" | "No" | "Error"
    reasoning: str = ""


@dataclass
class QARun:
    status: str  # "ok" | "error"
    error: str | None = None
    answer_text: str = ""
    sources: list[str] = field(default_factory=list)
    gen_time_sec: float = 0.0
    cost_usd: float = 0.0
    judge_verdict: QAVerdict | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


class QAJudge:
    """LLM-as-a-Judge для коротких фактологических ответов.

    Сравнивает свободный ответ системы с одним каноническим эталоном.
    Толерантен к перефразированиям, синонимам и доп. контексту, но
    отвергает уклончивые ответы и явные противоречия.

    Required env vars (положи в `.env`):
        JUDGE_API_KEY        — API-ключ судейской LLM

    Optional env vars:
        JUDGE_BASE_URL       — base URL OpenAI-совместимого API
        JUDGE_MODEL          — имя модели (default: gpt-4o-mini)
        JUDGE_TIMEOUT        — таймаут одного LLM-вызова, сек (default: 120)
        JUDGE_TEMPERATURE    — температура; если не задана, параметр не
                               передаётся (для reasoning-моделей, которые
                               принимают только дефолтное значение).
    """

    _SYSTEM_PROMPT = (
        "You are a strict QA judge. Given a question, a canonical reference "
        "answer (a short fact) and a system-generated answer, decide whether "
        "the system's answer correctly states the same fact. "
        "Accept paraphrases, synonyms, alternative spellings, transliterations "
        "and additional context — but reject answers that contradict the "
        "reference, omit the key fact, or hedge without committing. "
        'Reply with a single JSON object: {"correct": "Yes" | "No", '
        '"reasoning": "<one short sentence>"}. '
        "Output JSON only, no prose, no markdown fences."
    )

    def __init__(self) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise RuntimeError("openai package is not installed. Run: poetry install") from e

        api_key = os.environ.get("JUDGE_API_KEY")
        if not api_key:
            raise RuntimeError("JUDGE_API_KEY is not set. Add it to .env or export the variable.")

        base_url = os.environ.get("JUDGE_BASE_URL") or None
        timeout = float(os.environ.get("JUDGE_TIMEOUT", "120"))
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._model = os.environ.get("JUDGE_MODEL", "gpt-4o-mini")
        temp_raw = os.environ.get("JUDGE_TEMPERATURE")
        self._temperature: float | None = float(temp_raw) if temp_raw not in (None, "") else None

    async def verdict(self, question: str, canonical_answer: str, system_answer: str) -> QAVerdict:
        if not system_answer.strip():
            return QAVerdict(correct="No", reasoning="empty system answer")

        user_content = (
            f"Question:\n{question}\n\n"
            f"Canonical reference answer:\n{canonical_answer}\n\n"
            f"System answer (may be truncated):\n{system_answer[:6000]}\n\n"
            'Reply with JSON only: {"correct": "Yes" | "No", "reasoning": "<one short sentence>"}'
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
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            return QAVerdict(correct="Error", reasoning=f"llm error: {type(e).__name__}: {e}")

        content = (response.choices[0].message.content or "").strip()
        return self._parse_verdict(content)

    @staticmethod
    def _parse_verdict(content: str) -> QAVerdict:
        """Парсит ответ модели в QAVerdict. Терпим к шуму вокруг JSON."""
        m = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
                v_raw = str(parsed.get("correct", "")).strip().lower()
                reasoning = str(parsed.get("reasoning", "") or "").strip()
                if v_raw.startswith("y"):
                    return QAVerdict(correct="Yes", reasoning=reasoning or "matches reference")
                if v_raw.startswith("n"):
                    return QAVerdict(correct="No", reasoning=reasoning or "does not match reference")
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass
        low = content.lower()
        if re.search(r"\byes\b", low) and not re.search(r"\bno\b", low):
            return QAVerdict(correct="Yes", reasoning=content[:200])
        return QAVerdict(correct="No", reasoning=content[:200] or "unparseable judge response")


class MockQAJudge:
    async def verdict(self, question: str, canonical_answer: str, system_answer: str) -> QAVerdict:
        rng = random.Random(hash((question, canonical_answer, system_answer)))
        v = "Yes" if rng.random() > 0.3 else "No"
        return QAVerdict(correct=v, reasoning=f"[mock: {v}]")


def compute_qa_metrics(run: QARun) -> dict[str, Any]:
    n_sources = len(run.sources)
    unique_domains = len({urlparse(u).netloc for u in run.sources if u})
    verdict = run.judge_verdict.correct if run.judge_verdict else "Error"
    return {
        "correct": verdict,
        "n_sources": n_sources,
        "unique_domains": unique_domains,
        "gen_time_sec": run.gen_time_sec,
        "cost_usd": run.cost_usd,
    }


async def run_one_qa_system(
    runner: SystemRunner,
    prompt: str,
    canonical_answer: str,
    judge: QAJudge | MockQAJudge,
) -> dict[str, Any]:
    try:
        answer, sources, gen_time, cost = await runner.run(prompt)
    except Exception as e:
        return asdict(QARun(status="error", error=f"{type(e).__name__}: {e}"))

    run = QARun(
        status="ok",
        answer_text=answer,
        sources=sources,
        gen_time_sec=gen_time,
        cost_usd=cost,
    )
    run.judge_verdict = await judge.verdict(prompt, canonical_answer, answer)
    run.metrics = compute_qa_metrics(run)
    return asdict(run)


async def run_one_qa_case(
    case: dict[str, Any],
    runner: SystemRunner,
    judge: QAJudge | MockQAJudge,
) -> dict[str, Any]:
    started_at = datetime.now(UTC).isoformat()
    system_result = await run_one_qa_system(runner, case["prompt"], case["canonical_answer"], judge)
    return {
        "case_id": case["id"],
        "difficulty": case["difficulty"],
        "topic": case.get("topic", ""),
        "prompt": case["prompt"],
        "canonical_answer": case["canonical_answer"],
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "systems": {runner.name: system_result},
    }


def load_completed_case_ids(output_path: Path, system_name: str) -> set[str]:
    """Возвращает case_id с УСПЕШНЫМ запуском выбранной системы.

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
    """Удаляет из output записи с `status == "error"` для выбранной системы.

    Перезаписывает файл атомарно (через temp + rename). Возвращает количество
    удалённых записей.
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


def default_output_for(system: str) -> Path:
    return Path(f"data/results-qa-{system.replace('_', '-')}.jsonl")


def build_qa_judge(mock: bool) -> QAJudge | MockQAJudge:
    return MockQAJudge() if mock else QAJudge()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run short-fact QA benchmark cases through one selected DeepResearch system."
    )
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
        help="Output JSONL (default: data/results-qa-{system}.jsonl).",
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
    judge = build_qa_judge(args.mock)
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
    judge: QAJudge | MockQAJudge,
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
                print(f"[{idx}/{total}] {case['id']} ({case['difficulty']}) starting...", flush=True)
                try:
                    rec = await run_one_qa_case(case, runner, judge)
                except Exception as e:
                    print(f"[{idx}/{total}] {case['id']} FAILED: {type(e).__name__}: {e}", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
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
                    f"correct={metrics.get('correct', 'ERR')} | "
                    f"n_sources={metrics.get('n_sources', 'ERR')}"
                )

        await asyncio.gather(*(process(i, c) for i, c in enumerate(cases, 1)))

    return successful


if __name__ == "__main__":
    asyncio.run(main())
