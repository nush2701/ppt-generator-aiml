"""Deterministic tests for experiment pairing, reductions, and append-only output."""

import json
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.models.full_regeneration import FullRegenerationStatus
from app.models.metrics import OperationType
from app.models.presentation import Presentation
from app.models.selective_regeneration import SelectiveRegenerationStatus
from app.services.metrics import MetricsStore, RunMetricsCollector as RealRunMetricsCollector
from app.services.presentation_store import PresentationStore as RealPresentationStore
import run_experiment as experiment


def sample_presentation(presentation_id: str) -> Presentation:
    return Presentation.model_validate(
        {
            "id": presentation_id,
            "title": "Renewable Energy",
            "metadata": {
                "topic": "renewable energy",
                "purpose": "inform",
                "audience": "general audience",
                "slide_count": 3,
                "tone": "professional",
                "language": "English",
                "key_requirements": ["compare sources"],
                "constraints": [],
            },
            "slides": [
                {
                    "id": f"slide-{order}",
                    "order": order,
                    "layout": "title",
                    "purpose": f"Purpose {order}",
                    "components": [],
                }
                for order in range(1, 4)
            ],
        }
    )


class ExperimentTests(unittest.TestCase):
    def test_dataset_has_five_cases_and_three_modifications_each(self) -> None:
        cases = experiment._load_cases()
        self.assertEqual(len(cases), 5)
        self.assertTrue(all(len(case["modifications"]) == 3 for case in cases))

    def test_summary_calculates_reductions_and_handles_zero_denominators(self) -> None:
        def result(method: str, case_id: str, calls: int, tokens: int, latency: float, slides: int):
            return {
                "method": method,
                "case_id": case_id,
                "status": "regenerated",
                "llm_calls": calls,
                "total_tokens": tokens,
                "input_tokens": tokens // 2,
                "output_tokens": tokens - tokens // 2,
                "latency_ms": latency,
                "regenerated_slide_count": slides,
                "validation_errors": 0,
                "estimated_cost_usd": 0.0,
            }

        summary = experiment._build_summary(
            "exp-test",
            "2026-10-05T00:00:00+00:00",
            [
                result("selective", "pair-1", 2, 50, 100, 1),
                result("full", "pair-1", 2, 100, 200, 5),
            ],
        )
        self.assertEqual(summary["token_reduction_percent"], 50.0)
        self.assertEqual(summary["latency_reduction_percent"], 50.0)
        self.assertEqual(summary["call_reduction_percent"], 0.0)
        self.assertEqual(summary["slide_regeneration_reduction_percent"], 80.0)

        zero_summary = experiment._build_summary(
            "exp-zero",
            "2026-10-05T00:00:00+00:00",
            [
                result("selective", "pair-1", 0, 0, 0.0, 0),
                result("full", "pair-1", 0, 0, 0.0, 0),
            ],
        )
        self.assertIsNone(zero_summary["token_reduction_percent"])
        self.assertIsNone(zero_summary["latency_reduction_percent"])
        self.assertIsNone(zero_summary["call_reduction_percent"])
        self.assertIsNone(zero_summary["slide_regeneration_reduction_percent"])

    def test_limit_one_pairs_same_original_requirements_request_and_appends(self) -> None:
        root = Path(__file__).resolve().parent / "generated" / f"experiment_test_{uuid4().hex}"
        root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, root)
        cases_path = root / "experiment_cases.json"
        cases_path.write_text(
            json.dumps({"presentation_cases": experiment._load_cases()}), encoding="utf-8"
        )
        metrics_path = root / "metrics.jsonl"
        original_bytes: dict[str, bytes] = {}
        calls: list[dict[str, object]] = []

        class FakeProvider:
            model = "deterministic-test-model"
            usage_records = []

        class FakeGenerator:
            def __init__(self, _provider):
                pass

            def generate_presentation(self, _prompt, presentation_id):
                presentation = sample_presentation(presentation_id)
                path = RealPresentationStore(root / "generated").save(presentation, version=1)
                original_bytes[presentation_id] = path.read_bytes()
                return SimpleNamespace(presentation=presentation, output_path=path.with_suffix(".pptx"))

        class FakeSelective:
            def __init__(self, _provider):
                pass

            def selectively_regenerate(self, presentation, requirements, request):
                calls.append({
                    "method": "selective",
                    "presentation": presentation.model_dump(mode="json"),
                    "requirements": requirements.model_dump(mode="json"),
                    "request": request,
                })
                return SimpleNamespace(
                    status=SelectiveRegenerationStatus.REGENERATED,
                    regenerated_slides=["slide-2"],
                    affected_slides=["slide-2"],
                    message="ok",
                    output_path=root / "selective.pptx",
                )

        class FakeFull:
            def __init__(self, _provider):
                pass

            def fully_regenerate(self, presentation, requirements, request):
                calls.append({
                    "method": "full",
                    "presentation": presentation.model_dump(mode="json"),
                    "requirements": requirements.model_dump(mode="json"),
                    "request": request,
                })
                return SimpleNamespace(
                    status=FullRegenerationStatus.REGENERATED,
                    regenerated_slides=["slide-1", "slide-2", "slide-3"],
                    validation_errors=0,
                    message="ok",
                    output_path=root / "full.pptx",
                )

        def collector_factory(**kwargs):
            return RealRunMetricsCollector(
                **kwargs,
                store=MetricsStore(metrics_path),
            )

        patches = [
            patch.object(experiment, "CASES_PATH", cases_path),
            patch.object(experiment, "RESULTS_DIR", root / "results"),
            patch.object(experiment, "RESULTS_PATH", root / "results" / "experiment_results.jsonl"),
            patch.object(experiment, "SUMMARY_PATH", root / "results" / "experiment_summary.json"),
            patch.object(experiment, "PresentationStore", lambda: RealPresentationStore(root / "generated")),
            patch.object(experiment, "PresentationGenerator", FakeGenerator),
            patch.object(experiment, "GeminiProvider", FakeProvider),
            patch.object(experiment, "SelectiveRegenerator", FakeSelective),
            patch.object(experiment, "FullRegenerator", FakeFull),
            patch.object(experiment, "RunMetricsCollector", collector_factory),
        ]
        for item in patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])

        first_experiment = experiment.run_experiment(limit=1)
        second_experiment = experiment.run_experiment(limit=1)

        results = [
            json.loads(line)
            for line in (root / "results" / "experiment_results.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(results), 4)
        self.assertEqual({item["experiment_id"] for item in results[:2]}, {first_experiment})
        self.assertEqual({item["experiment_id"] for item in results[2:]}, {second_experiment})
        for pair in (results[:2], results[2:]):
            self.assertEqual(len({item["presentation_id"] for item in pair}), 1)
            self.assertEqual(len({item["modification_request"] for item in pair}), 1)
            self.assertEqual({item["method"] for item in pair}, {"selective", "full"})
            selective = next(item for item in pair if item["method"] == "selective")
            full = next(item for item in pair if item["method"] == "full")
            self.assertEqual(selective["regenerated_slide_count"], 1)
            self.assertEqual(full["regenerated_slide_count"], 3)
            self.assertTrue(selective["run_id"])
            self.assertTrue(full["run_id"])

        self.assertEqual(calls[0]["presentation"], calls[1]["presentation"])
        self.assertEqual(calls[0]["requirements"], calls[1]["requirements"])
        self.assertEqual(calls[0]["request"], calls[1]["request"])
        for presentation_id, before in original_bytes.items():
            stored_path = root / "generated" / f"presentation_{presentation_id}_v1.json"
            self.assertEqual(stored_path.read_bytes(), before)

        metric_records = MetricsStore(metrics_path).load_all()
        self.assertEqual(len(metric_records), 6)  # one initial generation and both methods per run
        summary_history = json.loads(
            (root / "results" / "experiment_summary.json").read_text(encoding="utf-8")
        )["experiments"]
        self.assertEqual(len(summary_history), 2)


if __name__ == "__main__":
    unittest.main()
