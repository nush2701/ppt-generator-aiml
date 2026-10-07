"""Deterministic validation and aggregation tests for human quality ratings."""

import csv
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError

from app.models.quality import (
    BlindedLabel,
    QualityEvaluationCase,
    QualityEvaluationMapping,
    QualityRating,
    RegenerationMethod,
)
import app.services.quality_evaluation as quality


def pair_fixture():
    selective_id = quality._new_evaluation_id()
    full_id = quality._new_evaluation_id()
    cases = [
        QualityEvaluationCase(
            evaluation_id=selective_id,
            experiment_id="exp-fixture",
            case_id="case-1",
            presentation_case_id="topic-1",
            modification_request="Change slide 2.",
            method="selective",
            original_presentation_id="presentation-1",
            output_pptx_path="selective.pptx",
            affected_slide_ids=["slide-2"],
            blinded_pptx_path="a.pptx",
            original_pptx_path="original.pptx",
        ),
        QualityEvaluationCase(
            evaluation_id=full_id,
            experiment_id="exp-fixture",
            case_id="case-1",
            presentation_case_id="topic-1",
            modification_request="Change slide 2.",
            method="full",
            original_presentation_id="presentation-1",
            output_pptx_path="full.pptx",
            affected_slide_ids=["slide-1", "slide-2", "slide-3"],
            blinded_pptx_path="b.pptx",
            original_pptx_path="original.pptx",
        ),
    ]
    mappings = [
        QualityEvaluationMapping(
            evaluation_id=selective_id,
            blinded_label=BlindedLabel.VERSION_A,
            actual_method=RegenerationMethod.SELECTIVE,
        ),
        QualityEvaluationMapping(
            evaluation_id=full_id,
            blinded_label=BlindedLabel.VERSION_B,
            actual_method=RegenerationMethod.FULL,
        ),
    ]
    return cases, mappings


def rating(evaluation_id: str, label: str, evaluator: str, score: int = 4):
    return QualityRating(
        evaluation_id=evaluation_id,
        blinded_label=label,
        relevance=score,
        completeness=score,
        consistency=score,
        readability=score,
        layout_suitability=score,
        requirement_adherence=score,
        evaluator_id=evaluator,
    )


class QualityEvaluationTests(unittest.TestCase):
    def test_evaluation_case_generation_and_stable_blinding(self) -> None:
        root = Path(__file__).resolve().parent / "generated" / f"quality_test_{uuid4().hex}"
        root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, root)
        original_dir = root / "generated"
        output_dir = root / "outputs"
        original_dir.mkdir()
        output_dir.mkdir()

        config_path = Path(__file__).resolve().parent / "experiments" / "experiment_cases.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        result_lines = []
        localized = [
            (presentation, modification)
            for presentation in config["presentation_cases"]
            for modification in presentation["modifications"]
            if modification["kind"] != "global"
        ]
        self.assertEqual(len(localized), 10)
        for presentation, modification in localized:
            presentation_id = f"presentation-{presentation['case_id']}"
            original_path = original_dir / f"presentation_{presentation_id}_v1.pptx"
            original_path.write_bytes(b"original deck fixture")
            for method in ("selective", "full"):
                method_output = output_dir / f"{modification['case_id']}_{method}.pptx"
                method_output.write_bytes(f"{method} deck fixture".encode())
                result_lines.append(
                    {
                        "experiment_id": "exp-quality-fixture",
                        "case_id": modification["case_id"],
                        "presentation_case_id": presentation["case_id"],
                        "presentation_id": presentation_id,
                        "modification_request": modification["prompt"],
                        "method": method,
                        "status": "regenerated",
                        "affected_slide_ids": ["slide-2"] if method == "selective" else [f"slide-{i}" for i in range(1, 6)],
                        "output_path": str(method_output.resolve()),
                    }
                )
        result_path = root / "experiment_results.jsonl"
        result_path.write_text("\n".join(json.dumps(row) for row in result_lines) + "\n", encoding="utf-8")

        with patch.object(quality, "BACKEND_DIR", root):
            summary = quality.prepare_quality_evaluation(
                experiment_results_path=result_path,
                experiment_cases_path=config_path,
                output_dir=output_dir,
            )
            cases_path = output_dir / "quality_evaluation_cases.json"
            mapping_path = output_dir / "quality_evaluation_mapping.json"
            packet_path = output_dir / "quality_evaluator_packet.json"
            template_path = output_dir / "quality_ratings_template.csv"
            mapping_before = mapping_path.read_bytes()
            quality.prepare_quality_evaluation(
                experiment_results_path=result_path,
                experiment_cases_path=config_path,
                output_dir=output_dir,
            )

        case_data = json.loads(cases_path.read_text(encoding="utf-8"))
        mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))
        packet_data = json.loads(packet_path.read_text(encoding="utf-8"))
        self.assertEqual(case_data["experiment_id"], "exp-quality-fixture")
        self.assertEqual(len(case_data["cases"]), 20)
        self.assertEqual(len(mapping_data["mappings"]), 20)
        self.assertEqual(len(packet_data["presentations"]), 20)
        self.assertEqual(mapping_before, mapping_path.read_bytes())
        self.assertEqual(summary["number_of_cases"], 10)
        self.assertEqual(summary["number_of_prepared_presentations"], 20)
        self.assertEqual(summary["number_of_evaluated_presentations"], 0)
        self.assertEqual(summary["evaluation_status"], "pending_human_ratings")
        self.assertEqual(summary["selective_metrics"]["overall_average_quality_score"], None)
        self.assertTrue(all("method" not in row for row in packet_data["presentations"]))
        self.assertTrue(all("affected_slide_ids" not in row for row in packet_data["presentations"]))
        with template_path.open(encoding="utf-8-sig", newline="") as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 20)

    def test_blinded_mapping_requires_both_methods_and_distinct_labels(self) -> None:
        cases, mappings = pair_fixture()
        checked_cases, checked_mappings = quality.validate_evaluation_package(
            cases, mappings, {"case-1"}
        )
        self.assertEqual({case.method for case in checked_cases}, set(RegenerationMethod))
        self.assertEqual({item.blinded_label for item in checked_mappings}, set(BlindedLabel))
        with self.assertRaises(ValueError):
            quality.validate_evaluation_package(cases[:1], mappings[:1], {"case-1"})

    def test_rating_validation_and_duplicate_detection(self) -> None:
        cases, mappings = pair_fixture()
        valid = rating(cases[0].evaluation_id, "Version A", "reviewer-1")
        self.assertEqual(quality.validate_ratings([valid], cases, mappings), [valid])
        with self.assertRaisesRegex(ValueError, "Duplicate rating"):
            quality.validate_ratings([valid, valid], cases, mappings)
        wrong_label = rating(cases[0].evaluation_id, "Version B", "reviewer-2")
        with self.assertRaisesRegex(ValueError, "Blinded label"):
            quality.validate_ratings([wrong_label], cases, mappings)

    def test_score_range_and_integer_validation(self) -> None:
        cases, mappings = pair_fixture()
        base = {
            "evaluation_id": cases[0].evaluation_id,
            "blinded_label": "Version A",
            "evaluator_id": "reviewer-1",
            **{dimension: 3 for dimension in quality.SCORE_DIMENSIONS},
        }
        self.assertEqual(QualityRating.model_validate(base).overall_score(), 3.0)
        for invalid in (0, 6, 3.5, True, "4"):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                QualityRating.model_validate({**base, "relevance": invalid})
        with self.assertRaises(ValidationError):
            QualityRating.model_validate({**base, "evaluator_id": " "})
        with self.assertRaises(ValidationError):
            QualityRating.model_validate({**base, "evaluation_id": "case-1"})

    def test_overall_and_dimension_averages_and_method_aggregation(self) -> None:
        cases, mappings = pair_fixture()
        selective = QualityRating(
            evaluation_id=cases[0].evaluation_id,
            blinded_label="Version A",
            relevance=5,
            completeness=4,
            consistency=3,
            readability=4,
            layout_suitability=5,
            requirement_adherence=3,
            evaluator_id="reviewer-1",
        )
        full = rating(cases[1].evaluation_id, "Version B", "reviewer-1", score=3)
        self.assertEqual(selective.overall_score(), 4.0)
        summary = quality.build_quality_summary("exp-fixture", cases, mappings, [selective, full])
        self.assertEqual(summary["selective_metrics"]["average_relevance"], 5.0)
        self.assertEqual(summary["selective_metrics"]["average_consistency"], 3.0)
        self.assertEqual(summary["selective_metrics"]["overall_average_quality_score"], 4.0)
        self.assertEqual(summary["full_metrics"]["overall_average_quality_score"], 3.0)
        self.assertEqual(summary["selective_metrics"]["rating_count"], 1)
        another_selective_rating = rating(
            cases[0].evaluation_id, "Version A", "reviewer-2", score=2
        )
        multi_rating_summary = quality.build_quality_summary(
            "exp-fixture",
            cases,
            mappings,
            [selective, another_selective_rating, full],
        )
        self.assertGreater(
            multi_rating_summary["selective_metrics"]["standard_deviation_overall_quality"],
            0,
        )

    def test_quality_difference_includes_absolute_observed_difference(self) -> None:
        cases, mappings = pair_fixture()
        ratings = [
            rating(cases[0].evaluation_id, "Version A", "reviewer-1", score=4),
            rating(cases[1].evaluation_id, "Version B", "reviewer-1", score=3),
        ]
        difference = quality.build_quality_summary("exp-fixture", cases, mappings, ratings)["quality_difference"]
        self.assertEqual(difference["selective_minus_full"], 1.0)
        self.assertEqual(difference["absolute_difference"], 1.0)
        self.assertFalse(difference["within_0_5_observed_difference"])
        self.assertEqual(difference["interpretation"], "observed difference greater than 0.5 points")

    def test_missing_rating_handling_does_not_invent_scores(self) -> None:
        cases, mappings = pair_fixture()
        empty = quality.build_quality_summary("exp-fixture", cases, mappings, [])
        self.assertEqual(empty["evaluation_status"], "pending_human_ratings")
        self.assertEqual(empty["number_of_evaluated_presentations"], 0)
        self.assertIsNone(empty["selective_metrics"]["overall_average_quality_score"])
        self.assertIsNone(empty["quality_difference"]["absolute_difference"])

        partial = quality.build_quality_summary(
            "exp-fixture",
            cases,
            mappings,
            [rating(cases[0].evaluation_id, "Version A", "reviewer-1")],
        )
        self.assertEqual(partial["evaluation_status"], "in_progress")
        self.assertIsNone(partial["quality_difference"]["selective_minus_full"])
        self.assertEqual(partial["full_metrics"]["rating_count"], 0)


if __name__ == "__main__":
    unittest.main()
