"""Validate model inputs and generate the 3 x 5 FDS case matrix.

This module uses only the Python standard library.  It never launches FDS and
it refuses to generate cases while a required parameter is missing, assumed,
or otherwise not marked VERIFIED.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from model_logic import derive_core_speeds


ALLOWED_STATUS = {"VERIFIED", "ASSUMED", "MISSING"}
PARAMETER_KEYS = {"value", "unit", "source", "status", "required_for_generation"}
EXPECTED_FIRE_IDS = ("F1", "F2", "F3")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def load_parameters(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def is_parameter_record(value: Any) -> bool:
    return isinstance(value, dict) and bool(PARAMETER_KEYS.intersection(value))


def iter_parameter_records(value: Any, path: str = "") -> Iterable[tuple[str, dict[str, Any]]]:
    if is_parameter_record(value):
        yield path, value
        return
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            yield from iter_parameter_records(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_parameter_records(child, f"{path}[{index}]")


def _filled(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _record_value(record: dict[str, Any]) -> Any:
    return record["value"]


def validate_parameters(config: dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    meta = config.get("_meta", {})
    if meta.get("schema_version") != "1.0.0":
        result.errors.append("_meta.schema_version必须为1.0.0")
    if meta.get("installation_allowed") is not False:
        result.errors.append("_meta.installation_allowed必须保持false")

    records = list(iter_parameter_records(config))
    if not records:
        result.errors.append("参数文件中没有参数记录")

    for path, record in records:
        missing_keys = PARAMETER_KEYS.difference(record)
        if missing_keys:
            result.errors.append(f"{path}缺少字段: {', '.join(sorted(missing_keys))}")
            continue
        if record["status"] not in ALLOWED_STATUS:
            result.errors.append(f"{path}.status非法: {record['status']!r}")
        if not str(record["unit"]).strip():
            result.errors.append(f"{path}.unit不能为空")
        if not str(record["source"]).strip():
            result.errors.append(f"{path}.source不能为空")
        if not isinstance(record["required_for_generation"], bool):
            result.errors.append(f"{path}.required_for_generation必须为布尔值")
        if record.get("required_for_generation"):
            if not _filled(record.get("value")):
                result.errors.append(f"阻塞参数缺失: {path}")
            elif record.get("status") != "VERIFIED":
                result.errors.append(f"阻塞参数未经核实: {path} ({record.get('status')})")

    fires = config.get("fire_scenarios")
    if not isinstance(fires, list) or [item.get("id") for item in fires] != list(EXPECTED_FIRE_IDS):
        result.errors.append("fire_scenarios必须按F1、F2、F3顺序定义")

    rule = config.get("orientation", {}).get("fire_location_rule", {}).get("value")
    if rule != "longitudinal_midpoint":
        result.errors.append("火源位置规则必须为longitudinal_midpoint")

    speeds = config.get("ventilation", {}).get("core_speeds_m_s", {}).get("value")
    if _filled(speeds):
        if not isinstance(speeds, list) or len(speeds) != 5:
            result.errors.append("core_speeds_m_s必须恰含5个值")
        elif any(not isinstance(value, (int, float)) or value <= 0 for value in speeds):
            result.errors.append("五档核心风速必须为正数")
        elif any(left >= right for left, right in zip(speeds, speeds[1:])):
            result.errors.append("五档核心风速必须严格递增")

    transitions = config.get("ventilation", {}).get("transition_speeds_m_s", {}).get("value")
    if _filled(transitions) and _filled(speeds):
        try:
            expected_speeds = derive_core_speeds(transitions)
            if [float(value) for value in speeds] != expected_speeds:
                result.errors.append(
                    f"core_speeds_m_s必须由转折速度生成；期望{expected_speeds}，实际{speeds}"
                )
        except (TypeError, ValueError) as exc:
            result.errors.append(f"transition_speeds_m_s无效: {exc}")

    length = config.get("geometry", {}).get("length_m", {}).get("value")
    if _filled(length) and isinstance(fires, list):
        fire_x = float(length) / 2.0
        for fire in fires:
            burner = fire.get("burner_xb_m", {}).get("value")
            if _filled(burner):
                if not isinstance(burner, list) or len(burner) != 6:
                    result.errors.append(f"{fire.get('id')}.burner_xb_m必须包含6个坐标")
                else:
                    burner_center_x = (float(burner[0]) + float(burner[1])) / 2.0
                    if abs(burner_center_x - fire_x) > 1e-6:
                        result.errors.append(
                            f"{fire.get('id')}火源纵向中心{burner_center_x} m不等于隧道中点{fire_x} m"
                        )
            obstruction = fire.get("vehicle_obstruction_xb_m", {}).get("value")
            if _filled(obstruction) and (not isinstance(obstruction, list) or len(obstruction) != 6):
                result.errors.append(f"{fire.get('id')}.vehicle_obstruction_xb_m必须包含6个坐标")
            ramp = fire.get("hrr_ramp", {}).get("value")
            if _filled(ramp):
                try:
                    ramp_times = [float(point["time_s"]) for point in ramp]
                    ramp_fractions = [float(point["fraction"]) for point in ramp]
                    if ramp_times[0] != 0 or any(a >= b for a, b in zip(ramp_times, ramp_times[1:])):
                        result.errors.append(f"{fire.get('id')}.hrr_ramp时间必须从0开始并严格递增")
                    if any(value < 0 or value > 1 for value in ramp_fractions):
                        result.errors.append(f"{fire.get('id')}.hrr_ramp比例必须位于[0,1]")
                    if ramp_fractions[0] != 0 or ramp_fractions[-1] != 1:
                        result.errors.append(f"{fire.get('id')}.hrr_ramp必须从0增长至1")
                except (KeyError, TypeError, ValueError, IndexError) as exc:
                    result.errors.append(f"{fire.get('id')}.hrr_ramp无效: {exc}")

    cross_passages = config.get("geometry", {}).get("cross_passages", {}).get("value")
    if _filled(cross_passages) and _filled(length):
        seen: set[str] = set()
        for passage in cross_passages:
            try:
                passage_id = str(passage["id"])
                x_m = float(passage["x_m"])
            except (KeyError, TypeError, ValueError) as exc:
                result.errors.append(f"横通道记录无效: {exc}")
                continue
            if passage_id in seen:
                result.errors.append(f"横通道ID重复: {passage_id}")
            seen.add(passage_id)
            if not 0 < x_m < float(length):
                result.errors.append(f"{passage_id}.x_m必须位于两个洞口之间")

    persistence = config.get("tenability", {}).get("persistence_s", {}).get("value")
    if _filled(persistence) and persistence <= 0:
        result.errors.append("tenability.persistence_s必须大于0")

    runs = config.get("evacuation", {}).get("runs_per_case", {}).get("value")
    if runs != 30:
        result.errors.append("evacuation.runs_per_case必须为30")

    return result


def build_case_matrix(config: dict[str, Any]) -> list[dict[str, Any]]:
    fires = config["fire_scenarios"]
    speeds = _record_value(config["ventilation"]["core_speeds_m_s"])
    if not isinstance(speeds, list) or len(speeds) != 5:
        raise ValueError("需要5个核心风速才能构建工况矩阵")

    cases: list[dict[str, Any]] = []
    for fire_index, fire in enumerate(fires, start=1):
        for speed_index, speed in enumerate(speeds, start=1):
            cases.append(
                {
                    "case_id": f"F{fire_index}_V{speed_index}",
                    "fire_id": fire["id"],
                    "power_symbol": fire["power_symbol"],
                    "fire_label": fire["label"],
                    "speed_id": f"V{speed_index}",
                    "speed_m_s": float(speed),
                }
            )
    return cases


def _format_xb(values: list[float]) -> str:
    if not isinstance(values, list) or len(values) != 6:
        raise ValueError("FDS XB必须包含6个数值")
    return ",".join(f"{float(value):.3f}" for value in values)


def _format_lines(lines: list[str], **values: Any) -> str:
    return "\n".join(line.format(**values) for line in lines)


def _fire_blocks(config: dict[str, Any], fire: dict[str, Any]) -> str:
    fire_id = fire["id"]
    fuel = _record_value(fire["fuel_id"])
    hrr_mw = float(_record_value(fire["hrr_peak_mw"]))
    hoc = float(_record_value(fire["heat_of_combustion_kj_kg"]))
    soot = float(_record_value(fire["soot_yield_kg_kg"]))
    co = float(_record_value(fire["co_yield_kg_kg"]))
    burner = _record_value(fire["burner_xb_m"])
    obstruction = _record_value(fire["vehicle_obstruction_xb_m"])
    ramp = _record_value(fire["hrr_ramp"])
    prefire_s = float(_record_value(config["simulation"]["prefire_duration_s"]))

    area_m2 = abs(float(burner[1]) - float(burner[0])) * abs(float(burner[3]) - float(burner[2]))
    if area_m2 <= 0:
        raise ValueError(f"{fire_id}燃烧面面积必须大于0")
    hrrpua = hrr_mw * 1000.0 / area_m2

    lines = [
        f"&REAC ID='{fire_id}_REACTION', FUEL='{fuel}', SOOT_YIELD={soot:.6g}, CO_YIELD={co:.6g}, HEAT_OF_COMBUSTION={hoc:.6g} /",
        f"&SURF ID='{fire_id}_FIRE', HRRPUA={hrrpua:.6g}, RAMP_Q='{fire_id}_RAMP', COLOR='RED' /",
    ]
    for point in ramp:
        lines.append(
            f"&RAMP ID='{fire_id}_RAMP', T={prefire_s + float(point['time_s']):.3f}, F={float(point['fraction']):.6g} /"
        )
    lines.extend(
        [
            f"&OBST XB={_format_xb(obstruction)}, SURF_ID='INERT' /",
            f"&VENT XB={_format_xb(burner)}, SURF_ID='{fire_id}_FIRE' /",
        ]
    )
    return "\n".join(lines)


def render_case(config: dict[str, Any], template: str, case: dict[str, Any]) -> str:
    fire = next(item for item in config["fire_scenarios"] if item["id"] == case["fire_id"])
    simulation = config["simulation"]
    prefire = float(_record_value(simulation["prefire_duration_s"]))
    postfire = float(_record_value(simulation["post_ignition_duration_s"]))
    speed = case["speed_m_s"]
    length_m = float(_record_value(config["geometry"]["length_m"]))
    fire_x_m = length_m / 2.0
    replacements = {
        "{{CASE_ID}}": case["case_id"],
        "{{CHID}}": f"nanwutai_{case['case_id'].lower()}",
        "{{TITLE}}": f"Nanwutai {case['case_id']} {case['fire_label']} {speed:.1f} m/s",
        "{{T_END_S}}": f"{prefire + postfire:.3f}",
        "{{AMBIENT_TEMPERATURE_C}}": f"{float(_record_value(simulation['ambient_temperature_c'])):.3f}",
        "{{MESH_BLOCKS}}": "\n".join(_record_value(simulation["mesh_blocks"])),
        "{{FIRE_BLOCKS}}": _fire_blocks(config, fire),
        "{{GEOMETRY_BLOCKS}}": "\n".join(_record_value(simulation["geometry_blocks"])),
        "{{BOUNDARY_BLOCKS}}": "\n".join(_record_value(simulation["boundary_blocks"])),
        "{{VELOCITY_BLOCKS}}": _format_lines(
            _record_value(config["ventilation"]["fds_velocity_lines_template"]),
            speed_m_s=f"{speed:.3f}",
            fire_x_m=f"{fire_x_m:.3f}",
        ),
        "{{DEVICE_BLOCKS}}": "\n".join(_record_value(simulation["device_blocks"])),
        "{{BREATHING_HEIGHT_M}}": f"{float(_record_value(config['tenability']['breathing_height_m'])):.3f}",
    }
    rendered = template
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    unresolved = sorted({part.split("}}", 1)[0] + "}}" for part in rendered.split("{{")[1:]})
    if unresolved:
        raise ValueError(f"模板仍含未替换标记: {', '.join(unresolved)}")
    return rendered


def write_cases(config: dict[str, Any], template_path: Path, output_dir: Path) -> list[dict[str, Any]]:
    validation = validate_parameters(config)
    if not validation.ok:
        raise ValueError("参数未通过生成门禁:\n- " + "\n- ".join(validation.errors))

    template = template_path.read_text(encoding="utf-8")
    cases = build_case_matrix(config)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"输出目录非空，拒绝覆盖: {output_dir}")
    staging = Path(tempfile.mkdtemp(prefix=".nanwutai-cases-", dir=output_dir.parent))
    try:
        for case in cases:
            rendered = render_case(config, template, case)
            (staging / f"{case['case_id']}.fds").write_text(rendered, encoding="utf-8", newline="\n")
        with (staging / "case_manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(cases[0]))
            writer.writeheader()
            writer.writerows(cases)
        (staging / "parameters_snapshot.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if output_dir.exists():
            output_dir.rmdir()
        staging.replace(output_dir)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return cases


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    model_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", type=Path, default=model_dir / "parameters.json")
    parser.add_argument("--template", type=Path, default=model_dir / "nanwutai_template.fds")
    parser.add_argument("--output", type=Path, default=model_dir.parent / "generated_cases")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)

    try:
        config = load_parameters(args.parameters)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取参数失败: {exc}", file=sys.stderr)
        return 2

    validation = validate_parameters(config)
    for warning in validation.warnings:
        print(f"WARNING: {warning}")
    if not validation.ok:
        print("模型尚未通过生成门禁:", file=sys.stderr)
        for error in validation.errors:
            print(f"- {error}", file=sys.stderr)
        return 2

    if args.validate_only:
        print("参数静态校验通过；未生成文件。")
        return 0

    try:
        cases = write_cases(config, args.template, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"生成失败: {exc}", file=sys.stderr)
        return 2
    print(f"已生成{len(cases)}个FDS输入骨架: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
