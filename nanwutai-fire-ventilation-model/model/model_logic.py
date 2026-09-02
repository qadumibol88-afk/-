"""Deterministic model logic for speed selection and ASET/RSET assessment."""

from __future__ import annotations

import math
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping, Sequence


def derive_core_speeds(transition_speeds_m_s: Mapping[str, float]) -> list[float]:
    """Derive five shared speeds from F1/F2/F3 backlayering transitions."""
    if set(transition_speeds_m_s) != {"F1", "F2", "F3"}:
        raise ValueError("转折风速必须且只能包含F1、F2、F3")
    values = [float(transition_speeds_m_s[key]) for key in ("F1", "F2", "F3")]
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("转折风速必须为有限正数")

    low = 0.75 * min(values)
    high = 1.25 * max(values)
    step = (high - low) / 4.0
    rounded = [
        float(Decimal(str(low + index * step)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        for index in range(5)
    ]
    for index in range(1, len(rounded)):
        if rounded[index] <= rounded[index - 1]:
            rounded[index] = float(
                Decimal(str(rounded[index - 1] + 0.1)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            )
    return rounded


def first_sustained_crossing(
    times_s: Sequence[float],
    values: Sequence[float],
    *,
    limit: float,
    direction: str,
    persistence_s: float,
) -> float | None:
    """Return the start of the first continuously violating interval."""
    if len(times_s) != len(values) or not times_s:
        raise ValueError("times_s和values必须等长且非空")
    if persistence_s <= 0:
        raise ValueError("persistence_s必须大于0")
    times = [float(value) for value in times_s]
    if any(not math.isfinite(value) for value in times):
        raise ValueError("时间必须为有限数")
    if any(left >= right for left, right in zip(times, times[1:])):
        raise ValueError("时间必须严格递增")
    if direction not in {"gte", "lte"}:
        raise ValueError("direction必须为gte或lte")

    def violates(value: float) -> bool:
        numeric = float(value)
        return numeric >= limit if direction == "gte" else numeric <= limit

    start: float | None = None
    for time_s, value in zip(times, values):
        if violates(value):
            if start is None:
                start = time_s
            if time_s - start >= persistence_s:
                return start
        else:
            start = None
    return None


def compute_aset(
    sensor_series: Mapping[str, Sequence[tuple[Sequence[float], Sequence[float]]]],
    criteria: Mapping[str, Mapping[str, float | str]],
    *,
    persistence_s: float,
    simulation_end_s: float,
) -> dict[str, Any]:
    """Compute the earliest sustained failure across criteria and sensors."""
    if simulation_end_s <= 0:
        raise ValueError("simulation_end_s必须大于0")
    crossings: dict[str, float | None] = {}
    for criterion, settings in criteria.items():
        if criterion not in sensor_series or not sensor_series[criterion]:
            raise ValueError(f"缺少{criterion}测点时间序列")
        limit = float(settings["limit"])
        direction = str(settings["direction"])
        sensor_crossings = [
            first_sustained_crossing(
                times,
                values,
                limit=limit,
                direction=direction,
                persistence_s=persistence_s,
            )
            for times, values in sensor_series[criterion]
        ]
        valid = [value for value in sensor_crossings if value is not None]
        crossings[criterion] = min(valid) if valid else None

    finite = {name: value for name, value in crossings.items() if value is not None}
    if not finite:
        return {
            "aset_s": float(simulation_end_s),
            "censored": True,
            "controlling_criterion": None,
            "criterion_crossings_s": crossings,
        }
    controlling = min(finite, key=lambda name: float(finite[name]))
    return {
        "aset_s": float(finite[controlling]),
        "censored": False,
        "controlling_criterion": controlling,
        "criterion_crossings_s": crossings,
    }


def nearest_rank_percentile(values: Iterable[float], percentile: float = 0.95) -> float:
    """Return a deterministic nearest-rank percentile."""
    samples = sorted(float(value) for value in values)
    if not samples:
        raise ValueError("百分位计算至少需要一个样本")
    if not 0 < percentile <= 1:
        raise ValueError("percentile必须位于(0,1]")
    if any(not math.isfinite(value) for value in samples):
        raise ValueError("样本必须为有限数")
    rank = max(1, math.ceil(percentile * len(samples)))
    return samples[rank - 1]


def aggregate_rset_runs(
    records: Sequence[Mapping[str, Any]], *, expected_runs: int = 30
) -> list[dict[str, Any]]:
    """Aggregate seed-level Pathfinder passage completion times to RSET P95."""
    if expected_runs <= 0:
        raise ValueError("expected_runs必须大于0")
    groups: dict[tuple[str, float, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        key = (str(record["fire_id"]), float(record["speed_m_s"]), str(record["passage_id"]))
        groups[key].append(record)
    summaries: list[dict[str, Any]] = []
    for (fire_id, speed, passage_id), group in sorted(groups.items()):
        seeds = [int(record["seed"]) for record in group]
        if len(set(seeds)) != expected_runs or len(group) != expected_runs:
            raise ValueError(
                f"{fire_id}/{speed}/{passage_id}需要{expected_runs}个唯一种子，实际{len(set(seeds))}"
            )
        used_records = [record for record in group if bool(record.get("used"))]
        if not used_records:
            summaries.append(
                {
                    "fire_id": fire_id,
                    "speed_m_s": speed,
                    "passage_id": passage_id,
                    "used": False,
                    "usage_rate": 0.0,
                    "rset_s": None,
                }
            )
            continue
        completion_times = []
        for record in used_records:
            completion = record.get("completion_s")
            if completion is None or completion == "":
                raise ValueError(f"{fire_id}/{speed}/{passage_id}已使用记录缺少completion_s")
            completion_times.append(float(completion))
        summaries.append(
            {
                "fire_id": fire_id,
                "speed_m_s": speed,
                "passage_id": passage_id,
                "used": True,
                "usage_rate": len(used_records) / expected_runs,
                "rset_s": nearest_rank_percentile(completion_times, 0.95),
            }
        )
    return summaries


def evaluate_record(
    aset_s: float,
    rset_s: float,
    *,
    minimum_margin_s: float = 60.0,
    minimum_ratio: float = 1.5,
) -> dict[str, float | bool]:
    if aset_s < 0 or rset_s <= 0:
        raise ValueError("ASET必须非负且RSET必须大于0")
    margin = float(aset_s) - float(rset_s)
    ratio = float(aset_s) / float(rset_s)
    return {
        "margin_s": margin,
        "aset_rset_ratio": ratio,
        "passes": margin >= minimum_margin_s and ratio >= minimum_ratio,
    }


def recommend_minimum_speed(
    records: Sequence[Mapping[str, Any]],
    *,
    expected_fire_ids: Sequence[str] = ("F1", "F2", "F3"),
    minimum_margin_s: float = 60.0,
    minimum_ratio: float = 1.5,
) -> dict[str, Any]:
    """Select the lowest speed passing every used passage for every fire."""
    by_speed: dict[float, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        by_speed[float(record["speed_m_s"])].append(record)
    if not by_speed:
        raise ValueError("没有安全评估记录")

    assessments: list[dict[str, Any]] = []
    expected = set(expected_fire_ids)
    for speed in sorted(by_speed):
        speed_records = by_speed[speed]
        used = [record for record in speed_records if bool(record.get("used"))]
        represented = {str(record["fire_id"]) for record in used}
        failures: list[str] = []
        if represented != expected:
            missing = ",".join(sorted(expected.difference(represented)))
            extra = ",".join(sorted(represented.difference(expected)))
            failures.append(f"火灾覆盖不完整 missing={missing or '-'} extra={extra or '-'}")
        for record in used:
            assessment = evaluate_record(
                float(record["aset_s"]),
                float(record["rset_s"]),
                minimum_margin_s=minimum_margin_s,
                minimum_ratio=minimum_ratio,
            )
            if not assessment["passes"]:
                failures.append(f"{record['fire_id']}/{record['passage_id']}未通过")
        assessments.append({"speed_m_s": speed, "passes": not failures, "failures": failures})

    recommendation = next((item["speed_m_s"] for item in assessments if item["passes"]), None)
    return {
        "recommended_speed_m_s": recommendation,
        "status": "FEASIBLE" if recommendation is not None else "NO_FEASIBLE_SPEED_IN_RANGE",
        "speed_assessments": assessments,
    }
