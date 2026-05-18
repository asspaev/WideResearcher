"""Aggregate per-case QA metrics from the three benchmark JSONL files.

Reads `data/results-qa-{system}.jsonl` for each system, computes accuracy
(доля Yes-вердиктов) и средние стоимостно-временные метрики (overall, по
уровням сложности и по темам), и пишет агрегат в
`data/aggregated-qa-metrics.json`. Дополнительно — сравнение accuracy
WideResearcher vs OSS DR (контроль одной и той же базовой модели).

Usage:
    python scripts/aggregate_qa_metrics.py
    python scripts/aggregate_qa_metrics.py --data-dir data --output data/aggregated-qa-metrics.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SYSTEM_FILES = {
    "openai_dr": "results-qa-openai-dr.jsonl",
    "wide_researcher": "results-qa-wide-researcher.jsonl",
    "oss_dr": "results-qa-oss-dr.jsonl",
}

# Числовые поля из system_result.metrics, которые усредняем.
METRIC_FIELDS = (
    "n_sources",
    "unique_domains",
    "gen_time_sec",
    "cost_usd",
)
# Верхнеуровневые поля внутри system_result (дубль метрик, оставляем для совместимости).
RUN_FIELDS = ("gen_time_sec", "cost_usd")

DIFFICULTY_LEVELS = ("easy", "medium", "hard")


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


def extract_system_run(case: dict[str, Any]) -> dict[str, Any] | None:
    """Return the single-system run dict from `case.systems`, or None on error."""
    systems = case.get("systems") or {}
    if not systems:
        return None
    run = next(iter(systems.values()))
    if run.get("status") != "ok":
        return None
    return run


def mean_std(values: list[float]) -> tuple[float | None, float | None]:
    """Sample mean and standard deviation. Returns (None, None) for empty input."""
    if not values:
        return None, None
    avg = statistics.fmean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return avg, std


def aggregate_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute accuracy and mean ± std across a list of system-run dicts."""
    n = len(runs)
    n_correct = sum(1 for r in runs if (r.get("metrics") or {}).get("correct") == "Yes")
    n_incorrect = sum(1 for r in runs if (r.get("metrics") or {}).get("correct") == "No")
    n_error = sum(1 for r in runs if (r.get("metrics") or {}).get("correct") == "Error")
    n_judged = n_correct + n_incorrect

    result: dict[str, Any] = {
        "n_cases": n,
        "n_correct": n_correct,
        "n_incorrect": n_incorrect,
        "n_judge_error": n_error,
        # accuracy — пессимистичная: судейские ошибки идут как невалид.
        "accuracy": (n_correct / n) if n else None,
        # accuracy_judged — честная: только среди реально оценённых.
        "accuracy_judged": (n_correct / n_judged) if n_judged else None,
    }

    for field in METRIC_FIELDS:
        values = [(r.get("metrics") or {}).get(field) for r in runs if (r.get("metrics") or {}).get(field) is not None]
        avg, std = mean_std([float(v) for v in values])
        result[f"avg_{field}"] = avg
        result[f"std_{field}"] = std

    for field in RUN_FIELDS:
        values = [r.get(field) for r in runs if r.get(field) is not None]
        avg, std = mean_std([float(v) for v in values])
        result[f"avg_{field}"] = avg
        result[f"std_{field}"] = std

    return result


def group_runs(
    cases_by_system: dict[str, list[dict[str, Any]]],
    key: str | None = None,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Group system runs by a case-level key (`difficulty` or `topic`).

    If `key` is None, returns a single "all" bucket.
    Output: {bucket_value: {system_name: [run, run, ...]}}.
    """
    buckets: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for system, cases in cases_by_system.items():
        for case in cases:
            bucket = "all" if key is None else case.get(key, "unknown")
            run = extract_system_run(case)
            if run is None:
                continue
            buckets.setdefault(bucket, {}).setdefault(system, []).append(run)
    return buckets


def aggregate_buckets(
    buckets: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        bucket: {system: aggregate_runs(runs) for system, runs in by_system.items()}
        for bucket, by_system in buckets.items()
    }


def compare_wr_vs_oss(overall: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """B vs C control: accuracy(WideResearcher) vs accuracy(OSS DR).

    Не гипотеза из new-metrics.md (там QA-бенчмарка нет), а вспомогательное
    сравнение — даёт картину «как WR отвечает на короткие факты относительно
    конкурирующего OSS-аналога на той же базовой модели».
    """
    wr = overall.get("wide_researcher", {}).get("accuracy")
    oss = overall.get("oss_dr", {}).get("accuracy")
    delta: float | None = None
    ratio: float | None = None
    if wr is not None and oss is not None:
        delta = wr - oss
        ratio = (wr / oss) if oss > 0 else None
    return {
        "metric": "accuracy",
        "accuracy_wide_researcher": wr,
        "accuracy_oss_dr": oss,
        "delta_wr_minus_oss": delta,
        "ratio_wr_over_oss": ratio,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("data/aggregated-qa-metrics.json"))
    args = parser.parse_args()

    cases_by_system: dict[str, list[dict[str, Any]]] = {}
    for system, filename in SYSTEM_FILES.items():
        path = args.data_dir / filename
        if not path.exists():
            print(f"warning: {path} not found, skipping {system}")
            continue
        cases_by_system[system] = load_cases(path)
        print(f"loaded {len(cases_by_system[system])} cases for {system}")

    overall = aggregate_buckets(group_runs(cases_by_system, key=None)).get("all", {})
    by_difficulty = aggregate_buckets(group_runs(cases_by_system, key="difficulty"))
    by_topic = aggregate_buckets(group_runs(cases_by_system, key="topic"))

    by_difficulty_ordered = {level: by_difficulty[level] for level in DIFFICULTY_LEVELS if level in by_difficulty}
    for level in by_difficulty:
        if level not in by_difficulty_ordered:
            by_difficulty_ordered[level] = by_difficulty[level]
    by_topic_ordered = {topic: by_topic[topic] for topic in sorted(by_topic)}

    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "systems": list(cases_by_system.keys()),
        "case_counts": {sys: len(cases) for sys, cases in cases_by_system.items()},
        "wr_vs_oss": compare_wr_vs_oss(overall),
        "overall": overall,
        "by_difficulty": by_difficulty_ordered,
        "by_topic": by_topic_ordered,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {args.output}")

    print("\nWR vs OSS:", output["wr_vs_oss"])
    print("\nOverall accuracy:")
    for system, agg in overall.items():
        acc = agg.get("accuracy")
        print(
            f"  {system:<18} {acc:.3f}  "
            f"(correct={agg['n_correct']}/{agg['n_cases']}, "
            f"no={agg['n_incorrect']}, err={agg['n_judge_error']})"
        )


if __name__ == "__main__":
    main()
