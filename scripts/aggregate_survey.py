"""Aggregate survey results for H4 (segment-level citations) and H5 (feedback-aware versioning).

Reads `data/results-survey.json` (manually exported from Google/Yandex Forms),
computes mean ± std for trust/verifiability/quality/usability × {A, B, C},
evaluates H4 / H5 acceptance criteria from `docs/research/survey-h4-h5.md`
(раздел 6.2), and writes the aggregate to `data/aggregated-survey-metrics.json`.

Output schema mirrors `aggregate_metrics.py`:
    * `likert_by_variant[variant][metric] = {avg, std, n, distribution}`
    * `delta_summary[delta_name] = {mean, std, min, max, n}`
    * `h4_check`, `h5_check` — paired t-test и Wilcoxon вместе с verdict-ом.

Usage:
    python scripts/aggregate_survey.py
    python scripts/aggregate_survey.py --input data/results-survey.json --output data/aggregated-survey-metrics.json
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path("data/results-survey.json")
DEFAULT_OUTPUT = Path("data/aggregated-survey-metrics.json")

# Позиционные индексы внутри одного респондента (list[[question, answer], ...]).
# Структура одинакова у всех ответов — Google/Yandex Forms экспортируют поля в фиксированном порядке.
IDX_ROLE = 2
IDX_FREQ = 3
IDX_EXPERIENCE = 4
RANK_INDICES = {"A": 17, "B": 18, "C": 19}

VARIANT_METRIC_INDICES: dict[tuple[str, str], int] = {
    ("A", "trust"): 5,
    ("A", "verifiability"): 6,
    ("A", "quality"): 7,
    ("A", "usability"): 8,
    ("B", "trust"): 9,
    ("B", "verifiability"): 10,
    ("B", "quality"): 11,
    ("B", "usability"): 12,
    ("C", "trust"): 13,
    ("C", "verifiability"): 14,
    ("C", "quality"): 15,
    ("C", "usability"): 16,
}

VARIANTS = ("A", "B", "C")
METRICS = ("trust", "verifiability", "quality", "usability")

LIKERT_THRESHOLD = 1.0  # Порог mean(Δ) из section 6.2
P_THRESHOLD = 0.05
SCREENING_EXCLUDE_FREQ = "Реже / почти не пользуюсь"

Respondent = list[list[str]]


def value_at(respondent: Respondent, idx: int) -> str:
    return respondent[idx][1]


def likert(respondent: Respondent, variant: str, metric: str) -> int:
    return int(value_at(respondent, VARIANT_METRIC_INDICES[(variant, metric)]).strip())


def is_screened_in(respondent: Respondent) -> bool:
    return value_at(respondent, IDX_FREQ) != SCREENING_EXCLUDE_FREQ


def _phi(z: float) -> float:
    """Standard-normal CDF через `math.erf`."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _average_ranks(values: list[float]) -> list[float]:
    """Ранги (1-based) с усреднением по группам ties."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j + 2) / 2.0  # mean(i+1 .. j+1) для 1-based рангов
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def paired_t_test(differences: list[float]) -> dict[str, Any]:
    """Парный t-test разностей против 0.

    P-value считается через нормальную аппроксимацию: при df ≥ 30
    распределение Стьюдента отличается от стандартного нормального
    на <0.001 в районе порога 0.05 — этого хватает для приёмки.
    """
    n = len(differences)
    if n < 2:
        return {"n": n, "mean": None, "std": None, "t": None, "df": None, "p_value_two_sided": None}
    mean = statistics.fmean(differences)
    sd = statistics.stdev(differences)
    if sd == 0:
        return {
            "n": n,
            "mean": mean,
            "std": sd,
            "t": math.inf if mean != 0 else 0.0,
            "df": n - 1,
            "p_value_two_sided": 0.0 if mean != 0 else 1.0,
        }
    t = mean / (sd / math.sqrt(n))
    p = 2.0 * (1.0 - _phi(abs(t)))
    return {"n": n, "mean": mean, "std": sd, "t": t, "df": n - 1, "p_value_two_sided": p}


def wilcoxon_signed_rank(differences: list[float]) -> dict[str, Any]:
    """Wilcoxon signed-rank test для парных разностей против 0.

    Нулевые разности отбрасываются (классическое правило). Для p-value
    используется нормальная аппроксимация с tie correction и
    continuity correction (стандарт для n ≥ 20).
    """
    nonzero = [d for d in differences if d != 0]
    n = len(nonzero)
    if n < 1:
        return {"n_nonzero": 0, "w_pos": None, "w_neg": None, "W": None, "z": None, "p_value_two_sided": None}

    abs_vals = [abs(d) for d in nonzero]
    ranks = _average_ranks(abs_vals)
    w_pos = sum(r for r, d in zip(ranks, nonzero, strict=True) if d > 0)
    w_neg = sum(r for r, d in zip(ranks, nonzero, strict=True) if d < 0)
    W = min(w_pos, w_neg)

    mean_W = n * (n + 1) / 4.0
    tie_groups = Counter(abs_vals)
    tie_correction = sum(t**3 - t for t in tie_groups.values() if t > 1)
    var_W = (n * (n + 1) * (2 * n + 1) - tie_correction / 2.0) / 24.0
    if var_W <= 0:
        return {"n_nonzero": n, "w_pos": w_pos, "w_neg": w_neg, "W": W, "z": None, "p_value_two_sided": None}

    # Continuity correction подталкивает W к среднему.
    if W < mean_W:
        z = (W - mean_W + 0.5) / math.sqrt(var_W)
    elif W > mean_W:
        z = (W - mean_W - 0.5) / math.sqrt(var_W)
    else:
        z = 0.0
    p = 2.0 * (1.0 - _phi(abs(z)))
    return {"n_nonzero": n, "w_pos": w_pos, "w_neg": w_neg, "W": W, "z": z, "p_value_two_sided": p}


def aggregate_likerts(respondents: list[Respondent]) -> dict[str, dict[str, dict[str, Any]]]:
    """Для каждой (variant, metric) → {avg, std, n, distribution{score: count}}."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for variant in VARIANTS:
        out[variant] = {}
        for metric in METRICS:
            values = [likert(r, variant, metric) for r in respondents]
            out[variant][metric] = {
                "avg": statistics.fmean(values) if values else None,
                "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                "n": len(values),
                "distribution": {str(score): count for score, count in sorted(Counter(values).items())},
            }
    return out


def compute_deltas(respondents: list[Respondent]) -> dict[str, list[int]]:
    """Парные дельты B−A и C−B по всем четырём метрикам."""
    deltas: dict[str, list[int]] = {}
    for metric in METRICS:
        deltas[f"{metric}_BminusA"] = [likert(r, "B", metric) - likert(r, "A", metric) for r in respondents]
        deltas[f"{metric}_CminusB"] = [likert(r, "C", metric) - likert(r, "B", metric) for r in respondents]
    return deltas


def summarise_deltas(deltas: dict[str, list[int]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, vals in deltas.items():
        out[name] = {
            "mean": statistics.fmean(vals) if vals else None,
            "std": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
            "n": len(vals),
        }
    return out


def evaluate_hypothesis(name: str, criterion: str, deltas: list[int]) -> dict[str, Any]:
    """Прогоняет приёмочные критерии H4/H5 на парных дельтах.

    Эффект считается подтверждённым, если mean(Δ) ≥ 1.0 **и** хотя бы один
    из двух тестов (t-test, Wilcoxon) даёт p < 0.05. Согласно section 6.2
    обоих тестов достаточно — берём минимум p, что соответствует выбору
    «paired t-test ИЛИ Wilcoxon».
    """
    diffs = [float(d) for d in deltas]
    mean = statistics.fmean(diffs) if diffs else None
    std = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
    t_result = paired_t_test(diffs)
    w_result = wilcoxon_signed_rank(diffs)
    effect_passed = mean is not None and mean >= LIKERT_THRESHOLD
    p_values = [p for p in (t_result.get("p_value_two_sided"), w_result.get("p_value_two_sided")) if p is not None]
    p_min = min(p_values) if p_values else None
    p_passed = p_min is not None and p_min < P_THRESHOLD
    verdict = "passed" if effect_passed and p_passed else "failed"
    return {
        "name": name,
        "criterion": criterion,
        "n": len(diffs),
        "mean_delta": mean,
        "std_delta": std,
        "threshold": LIKERT_THRESHOLD,
        "effect_passed": effect_passed,
        "p_threshold": P_THRESHOLD,
        "p_value_min": p_min,
        "p_value_passed": p_passed,
        "paired_t_test": t_result,
        "wilcoxon": w_result,
        "verdict": verdict,
    }


def demographics(respondents: list[Respondent]) -> dict[str, dict[str, int]]:
    return {
        "role": dict(Counter(value_at(r, IDX_ROLE) for r in respondents)),
        "frequency": dict(Counter(value_at(r, IDX_FREQ) for r in respondents)),
        "deep_research_experience": dict(Counter(value_at(r, IDX_EXPERIENCE) for r in respondents)),
    }


def ranking_distribution(respondents: list[Respondent]) -> dict[str, dict[str, int]]:
    """Сколько респондентов поставили каждому варианту место 1 / 2 / 3."""
    out: dict[str, dict[str, int]] = {}
    for variant, idx in RANK_INDICES.items():
        counts = Counter(value_at(r, idx) for r in respondents)
        out[variant] = {place: counts.get(place, 0) for place in ("1 место", "2 место", "3 место")}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    raw: list[Respondent] = json.loads(args.input.read_text(encoding="utf-8"))
    n_total = len(raw)
    respondents = [r for r in raw if is_screened_in(r)]
    n_screened_out = n_total - len(respondents)

    likerts = aggregate_likerts(respondents)
    deltas = compute_deltas(respondents)

    h4 = evaluate_hypothesis(
        name="H4",
        criterion="mean(Δtrust(B−A)) ≥ 1.0 AND p < 0.05 (paired t-test или Wilcoxon, H0: Δ = 0)",
        deltas=deltas["trust_BminusA"],
    )
    h5 = evaluate_hypothesis(
        name="H5",
        criterion="mean(Δquality(C−B)) ≥ 1.0 AND p < 0.05 (paired t-test или Wilcoxon, H0: Δ = 0)",
        deltas=deltas["quality_CminusB"],
    )

    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "n_total_respondents": n_total,
        "n_screened_out": n_screened_out,
        "n_analyzed": len(respondents),
        "demographics": demographics(respondents),
        "likert_by_variant": likerts,
        "delta_summary": summarise_deltas(deltas),
        "ranking_distribution": ranking_distribution(respondents),
        "h4_check": h4,
        "h5_check": h5,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {args.output}")

    print(f"\nn_analyzed: {len(respondents)} (screened_out: {n_screened_out})")
    print("\nMean ± std by variant:")
    for variant in VARIANTS:
        cells = ", ".join(f"{m}={likerts[variant][m]['avg']:.2f}±{likerts[variant][m]['std']:.2f}" for m in METRICS)
        print(f"  {variant}: {cells}")

    for check in (h4, h5):
        t = check["paired_t_test"]
        w = check["wilcoxon"]
        # Печатаем без Unicode-математики, иначе Windows cp1251 падает с UnicodeEncodeError.
        print(
            f"\n{check['name']}: mean(delta)={check['mean_delta']:.3f}+/-{check['std_delta']:.3f} "
            f"(threshold >= {check['threshold']}) | "
            f"t={t['t']:.2f}, p_t={t['p_value_two_sided']:.3g} | "
            f"Wilcoxon z={w['z']:.2f}, p_w={w['p_value_two_sided']:.3g} | "
            f"verdict: {check['verdict']}"
        )


if __name__ == "__main__":
    main()
