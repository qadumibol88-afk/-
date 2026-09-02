from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_DIR / "model"
sys.path.insert(0, str(MODEL_DIR))

from generate_cases import build_case_matrix, load_parameters, validate_parameters, write_cases
from analyze_safety import load_records
from model_logic import (
    aggregate_rset_runs,
    compute_aset,
    derive_core_speeds,
    evaluate_record,
    first_sustained_crossing,
    nearest_rank_percentile,
    recommend_minimum_speed,
)


class ParameterGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parameter_path = MODEL_DIR / "parameters.json"
        cls.template_path = MODEL_DIR / "nanwutai_template.fds"
        cls.config = load_parameters(cls.parameter_path)

    def test_current_parameters_are_intentionally_blocked(self) -> None:
        result = validate_parameters(self.config)
        self.assertFalse(result.ok)
        joined = "\n".join(result.errors)
        self.assertIn("阻塞参数未经核实: geometry.length_m (ASSUMED)", joined)
        self.assertIn("阻塞参数缺失: geometry.cross_section_yz_m", joined)
        self.assertIn("阻塞参数缺失: ventilation.core_speeds_m_s", joined)

    def test_failed_gate_writes_no_case_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "cases"
            with self.assertRaises(ValueError):
                write_cases(self.config, self.template_path, output)
            self.assertFalse(output.exists())

    def test_case_matrix_has_stable_fifteen_ids(self) -> None:
        config = copy.deepcopy(self.config)
        config["ventilation"]["core_speeds_m_s"]["value"] = [1.0, 1.5, 2.0, 2.5, 3.0]
        cases = build_case_matrix(config)
        self.assertEqual(len(cases), 15)
        self.assertEqual(cases[0]["case_id"], "F1_V1")
        self.assertEqual(cases[-1]["case_id"], "F3_V5")
        self.assertEqual(len({case["case_id"] for case in cases}), 15)

    def test_complete_synthetic_fixture_generates_fifteen_files(self) -> None:
        config = copy.deepcopy(self.config)
        geometry = config["geometry"]
        geometry["selected_bore"].update(value="SYNTHETIC", status="VERIFIED")
        geometry["length_m"].update(value=100.0, status="VERIFIED")
        geometry["cross_section_yz_m"].update(
            value=[[0, 0], [10, 0], [10, 5], [0, 5]], status="VERIFIED"
        )
        geometry["slope_profile_xz_m"].update(value=[[0, 0], [100, 1]], status="VERIFIED")
        geometry["cross_passages"].update(
            value=[{"id": "CP01", "x_m": 25.0}, {"id": "CP02", "x_m": 75.0}], status="VERIFIED"
        )
        geometry["safe_bore_stub_length_m"].update(value=20.0, status="VERIFIED")
        config["orientation"]["fire_center_y_m"].update(value=5.0, status="VERIFIED")
        for index, fire in enumerate(config["fire_scenarios"], start=1):
            fire["hrr_peak_mw"].update(value=5.0 * index, status="VERIFIED")
            fire["fuel_id"].update(value="PROPANE", status="VERIFIED")
            fire["heat_of_combustion_kj_kg"].update(value=46000.0, status="VERIFIED")
            fire["soot_yield_kg_kg"].update(value=0.05, status="VERIFIED")
            fire["co_yield_kg_kg"].update(value=0.01, status="VERIFIED")
            fire["hrr_ramp"].update(
                value=[{"time_s": 0, "fraction": 0}, {"time_s": 60, "fraction": 1}], status="VERIFIED"
            )
            fire["vehicle_obstruction_xb_m"].update(
                value=[48, 52, 4, 6, 0, 1], status="VERIFIED"
            )
            fire["burner_xb_m"].update(value=[49, 51, 4, 6, 1, 1], status="VERIFIED")
        ventilation = config["ventilation"]
        transitions = {"F1": 1.0, "F2": 1.5, "F3": 2.0}
        ventilation["transition_speeds_m_s"].update(value=transitions, status="VERIFIED")
        ventilation["core_speeds_m_s"].update(value=derive_core_speeds(transitions), status="VERIFIED")
        ventilation["fds_velocity_lines_template"].update(
            value=["&VENT XB=0,0,0,10,0,5, SURF_ID='INLET_{speed_m_s}' /"], status="VERIFIED"
        )
        for key, value in {
            "breathing_height_m": 1.8,
            "temperature_limit_c": 60.0,
            "visibility_limit_m": 10.0,
            "co_limit_ppm": 500.0,
            "smoke_layer_min_height_m": 2.0,
            "backlayer_visibility_threshold_m": 30.0,
            "ceiling_probe_offset_m": 0.2,
        }.items():
            config["tenability"][key].update(value=value, status="VERIFIED")
        simulation = config["simulation"]
        simulation["prefire_duration_s"].update(value=60.0, status="VERIFIED")
        simulation["post_ignition_duration_s"].update(value=600.0, status="VERIFIED")
        simulation["ambient_temperature_c"].update(value=20.0, status="VERIFIED")
        simulation["mesh_blocks"].update(
            value=["&MESH IJK=10,10,5, XB=0,100,0,10,0,5 /"], status="VERIFIED"
        )
        simulation["geometry_blocks"].update(value=["! synthetic geometry"], status="VERIFIED")
        simulation["boundary_blocks"].update(value=["! synthetic boundaries"], status="VERIFIED")
        simulation["device_blocks"].update(value=["! synthetic devices"], status="VERIFIED")

        validation = validate_parameters(config)
        self.assertTrue(validation.ok, "\n".join(validation.errors))
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "cases"
            cases = write_cases(config, self.template_path, output)
            self.assertEqual(len(cases), 15)
            self.assertEqual(len(list(output.glob("F*_V*.fds"))), 15)
            rendered = (output / "F1_V1.fds").read_text(encoding="utf-8")
            self.assertNotIn("{{", rendered)
            self.assertIn("nanwutai_f1_v1", rendered)

    def test_parameter_file_is_valid_json(self) -> None:
        loaded = json.loads(self.parameter_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["_meta"]["installation_allowed"], False)


class SpeedSelectionTests(unittest.TestCase):
    def test_derives_shared_five_speed_grid(self) -> None:
        self.assertEqual(
            derive_core_speeds({"F1": 2.0, "F2": 3.0, "F3": 4.0}),
            [1.5, 2.4, 3.3, 4.1, 5.0],
        )

    def test_rejects_incomplete_transition_set(self) -> None:
        with self.assertRaises(ValueError):
            derive_core_speeds({"F1": 2.0, "F2": 3.0})


class AsetLogicTests(unittest.TestCase):
    def test_sustained_crossing_returns_interval_start(self) -> None:
        time = [0, 5, 10, 15, 20]
        values = [20, 61, 62, 63, 64]
        self.assertEqual(
            first_sustained_crossing(time, values, limit=60, direction="gte", persistence_s=10),
            5,
        )

    def test_short_spike_does_not_trigger(self) -> None:
        time = [0, 5, 10, 15, 20, 25]
        values = [20, 61, 20, 61, 62, 63]
        self.assertEqual(
            first_sustained_crossing(time, values, limit=60, direction="gte", persistence_s=10),
            15,
        )

    def test_compute_aset_selects_earliest_criterion(self) -> None:
        time = [0, 5, 10, 15, 20]
        series = {
            "temperature": [(time, [20, 20, 61, 62, 63])],
            "visibility": [(time, [30, 9, 8, 7, 6])],
        }
        criteria = {
            "temperature": {"limit": 60, "direction": "gte"},
            "visibility": {"limit": 10, "direction": "lte"},
        }
        result = compute_aset(series, criteria, persistence_s=10, simulation_end_s=60)
        self.assertEqual(result["aset_s"], 5)
        self.assertEqual(result["controlling_criterion"], "visibility")
        self.assertFalse(result["censored"])

    def test_compute_aset_reports_right_censoring(self) -> None:
        time = [0, 5, 10]
        series = {"temperature": [(time, [20, 21, 22])]}
        criteria = {"temperature": {"limit": 60, "direction": "gte"}}
        result = compute_aset(series, criteria, persistence_s=10, simulation_end_s=60)
        self.assertEqual(result["aset_s"], 60)
        self.assertTrue(result["censored"])
        self.assertIsNone(result["controlling_criterion"])


class RsetAndRecommendationTests(unittest.TestCase):
    def test_nearest_rank_p95_for_thirty_runs(self) -> None:
        self.assertEqual(nearest_rank_percentile(range(1, 31), 0.95), 29)

    def test_aggregates_thirty_pathfinder_seeds(self) -> None:
        records = [
            {
                "fire_id": "F1",
                "speed_m_s": 1.5,
                "passage_id": "CP01",
                "seed": seed,
                "used": True,
                "completion_s": seed,
            }
            for seed in range(1, 31)
        ]
        summary = aggregate_rset_runs(records)
        self.assertEqual(summary[0]["rset_s"], 29)
        self.assertEqual(summary[0]["usage_rate"], 1.0)

    def test_rejects_incomplete_seed_set(self) -> None:
        records = [
            {
                "fire_id": "F1",
                "speed_m_s": 1.5,
                "passage_id": "CP01",
                "seed": seed,
                "used": True,
                "completion_s": seed,
            }
            for seed in range(1, 30)
        ]
        with self.assertRaises(ValueError):
            aggregate_rset_runs(records)

    def test_dual_safety_criterion(self) -> None:
        self.assertTrue(evaluate_record(300, 200)["passes"])
        self.assertFalse(evaluate_record(250, 200)["passes"])

    def test_selects_lowest_globally_passing_speed(self) -> None:
        records = []
        for speed in (1.0, 1.5, 2.0):
            for fire in ("F1", "F2", "F3"):
                aset = 250 if speed == 1.0 and fire == "F3" else 360
                records.append(
                    {
                        "fire_id": fire,
                        "speed_m_s": speed,
                        "passage_id": "CP01",
                        "used": True,
                        "aset_s": aset,
                        "rset_s": 200,
                    }
                )
        result = recommend_minimum_speed(records)
        self.assertEqual(result["status"], "FEASIBLE")
        self.assertEqual(result["recommended_speed_m_s"], 1.5)

    def test_unused_passage_is_not_fabricated_or_scored(self) -> None:
        records = [
            {"fire_id": fire, "speed_m_s": 2.0, "passage_id": "CP01", "used": True, "aset_s": 360, "rset_s": 200}
            for fire in ("F1", "F2", "F3")
        ]
        records.append(
            {"fire_id": "F1", "speed_m_s": 2.0, "passage_id": "CP02", "used": False, "aset_s": 0, "rset_s": 0}
        )
        result = recommend_minimum_speed(records)
        self.assertEqual(result["recommended_speed_m_s"], 2.0)

    def test_unused_passage_allows_blank_rset_in_csv(self) -> None:
        csv_text = (
            "fire_id,speed_m_s,passage_id,used,aset_s,aset_censored,rset_s\n"
            "F1,2.0,CP02,false,300,false,\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "unused.csv"
            path.write_text(csv_text, encoding="utf-8")
            records = load_records(path)
        self.assertFalse(records[0]["used"])
        self.assertIsNone(records[0]["rset_s"])


if __name__ == "__main__":
    unittest.main()
