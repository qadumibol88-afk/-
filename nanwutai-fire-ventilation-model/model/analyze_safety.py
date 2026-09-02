"""Summarize cross-passage ASET/RSET records and recommend a shared speed."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from model_logic import evaluate_record, recommend_minimum_speed


REQUIRED_COLUMNS = {
    "fire_id",
    "speed_m_s",
    "passage_id",
    "used",
    "aset_s",
    "aset_censored",
    "rset_s",
}


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"无法解析布尔值: {value!r}")


def load_records(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"输入CSV缺少列: {', '.join(sorted(missing))}")
        records: list[dict[str, object]] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                used = parse_bool(row["used"])
                rset_text = row["rset_s"].strip()
                if used and not rset_text:
                    raise ValueError("used=true时rset_s不能为空")
                records.append(
                    {
                        "fire_id": row["fire_id"].strip(),
                        "speed_m_s": float(row["speed_m_s"]),
                        "passage_id": row["passage_id"].strip(),
                        "used": used,
                        "aset_s": float(row["aset_s"]),
                        "aset_censored": parse_bool(row["aset_censored"]),
                        "rset_s": float(rset_text) if rset_text else None,
                    }
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"第{row_number}行无效: {exc}") from exc
    return records


def summarize(records: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    if not records:
        raise ValueError("输入CSV没有数据行")
    rows: list[dict[str, object]] = []
    for record in records:
        if not bool(record["used"]):
            rows.append({**record, "margin_s": "", "aset_rset_ratio": "", "passes": "UNUSED"})
            continue
        evaluation = evaluate_record(float(record["aset_s"]), float(record["rset_s"]))
        rows.append({**record, **evaluation})
    recommendation = recommend_minimum_speed(records)
    return rows, recommendation


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--summary-json", type=Path)
    args = parser.parse_args(argv)
    try:
        records = load_records(args.input_csv)
        rows, recommendation = summarize(records)
        if args.output_csv:
            if args.output_csv.exists():
                raise FileExistsError(f"拒绝覆盖已有文件: {args.output_csv}")
            with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        if args.summary_json:
            if args.summary_json.exists():
                raise FileExistsError(f"拒绝覆盖已有文件: {args.summary_json}")
            args.summary_json.write_text(
                json.dumps(recommendation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    except (OSError, ValueError, KeyError) as exc:
        print(f"安全评估失败: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(recommendation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
