"""Aggregate per-case metrics from the three benchmark JSONL files.

Reads `data/results-{system}.jsonl` for each system, computes mean ± std for
the metrics listed in `docs/research/new-metrics.md` section 1.4 (overall,
per category, per freshness level), and writes the aggregate to
`data/aggregated-metrics.json`. Also evaluates the H2 acceptance criterion
from section 1.6.

Usage:
    python scripts/aggregate_metrics.py
    python scripts/aggregate_metrics.py --data-dir data --output data/aggregated-metrics.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SYSTEM_FILES = {
    "openai_dr": "results-openai-dr.jsonl",
    "wide_researcher": "results-wide-researcher.jsonl",
    "oss_dr": "results-oss-dr.jsonl",
}

METRIC_FIELDS = (
    "n_sources",
    "n_valid",
    "n_invalid",
    "n_unreachable",
    "n_evaluable",
    "validity_rate",
    "validity_rate_evaluable",
    "unique_domains",
    "time_per_valid",
    "cost_per_valid",
)
# Top-level (not under .metrics) per-system fields we also aggregate.
RUN_FIELDS = ("gen_time_sec", "cost_usd")

FRESHNESS_LEVELS = ("low", "mid", "high")
H2_THRESHOLD = 1.15


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
    """Compute mean ± std for each metric across a list of system-run dicts."""
    result: dict[str, Any] = {"n_cases": len(runs)}

    for field in METRIC_FIELDS:
        # Filter out None (e.g. time_per_valid when n_valid == 0).
        values = [run["metrics"][field] for run in runs if run.get("metrics") and run["metrics"].get(field) is not None]
        avg, std = mean_std(values)
        result[f"avg_{field}"] = avg
        result[f"std_{field}"] = std
        result[f"n_{field}_observed"] = len(values)

    for field in RUN_FIELDS:
        values = [run[field] for run in runs if run.get(field) is not None]
        avg, std = mean_std(values)
        result[f"avg_{field}"] = avg
        result[f"std_{field}"] = std

    return result


def group_runs(
    cases_by_system: dict[str, list[dict[str, Any]]],
    key: str | None = None,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Group system runs by a case-level key (`category_code` or `freshness`).

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


def evaluate_h2(overall: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """H2 criterion: avg_n_valid(WR) >= 1.15 * avg_n_valid(OSS DR)."""
    wr = overall.get("wide_researcher", {}).get("avg_n_valid")
    oss = overall.get("oss_dr", {}).get("avg_n_valid")
    ratio: float | None = None
    verdict = "skipped"
    if wr is not None and oss is not None and oss > 0:
        ratio = wr / oss
        verdict = "passed" if ratio >= H2_THRESHOLD else "failed"
    return {
        "criterion": "avg_n_valid(wide_researcher) >= 1.15 * avg_n_valid(oss_dr)",
        "avg_n_valid_wide_researcher": wr,
        "avg_n_valid_oss_dr": oss,
        "threshold": H2_THRESHOLD,
        "ratio": ratio,
        "verdict": verdict,
    }


def category_names_from_cases(cases_by_system: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """Map category_code → category name (taken from any case that has it)."""
    names: dict[str, str] = {}
    for cases in cases_by_system.values():
        for case in cases:
            code = case.get("category_code")
            if code and code not in names and case.get("category"):
                names[code] = case["category"]
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("data/aggregated-metrics.json"))
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
    by_category = aggregate_buckets(group_runs(cases_by_system, key="category_code"))
    by_freshness = aggregate_buckets(group_runs(cases_by_system, key="freshness"))

    by_category_ordered = {code: by_category[code] for code in sorted(by_category)}
    by_freshness_ordered = {level: by_freshness[level] for level in FRESHNESS_LEVELS if level in by_freshness}
    for level in by_freshness:
        if level not in by_freshness_ordered:
            by_freshness_ordered[level] = by_freshness[level]

    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "systems": list(cases_by_system.keys()),
        "case_counts": {sys: len(cases) for sys, cases in cases_by_system.items()},
        "category_names": category_names_from_cases(cases_by_system),
        "h2_check": evaluate_h2(overall),
        "overall": overall,
        "by_category": by_category_ordered,
        "by_freshness": by_freshness_ordered,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {args.output}")

    print("\nH2 check:", output["h2_check"])
    print("\nOverall avg_n_valid:")
    for system, agg in overall.items():
        avg = agg.get("avg_n_valid")
        std = agg.get("std_n_valid")
        print(f"  {system:<18} {avg:.3f} ± {std:.3f}  (n={agg['n_cases']})")


if __name__ == "__main__":
    main()
