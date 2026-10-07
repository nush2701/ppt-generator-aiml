"""Deterministic tests for metrics records, collection, costing, and JSONL storage."""

import time
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from app.models.metrics import OperationType, RunMetrics
from app.services.metrics import (
    MetricsStore,
    RunMetricsCollector,
    calculate_estimated_cost,
)


def make_metrics(**overrides: object) -> RunMetrics:
    values: dict[str, object] = {
        "run_id": "run-test-1",
        "timestamp": "2026-10-05T12:00:00+00:00",
        "operation": OperationType.GENERATION,
        "presentation_id": "presentation-test-1",
        "modification_request": None,
        "status": "success",
        "model_name": "gemini-test-model",
        "latency_ms": 12.5,
        "llm_calls": 1,
        "input_tokens": 20,
        "output_tokens": 15,
        "total_tokens": 35,
        "token_usage_available": True,
        "usage_unavailable_calls": 0,
        "regenerated_slide_count": 5,
        "total_slide_count": 5,
        "validation_errors": 0,
        "estimated_cost_usd": 0.0,
        "affected_slide_ids": [],
    }
    values.update(overrides)
    return RunMetrics.model_validate(values)


def main() -> None:
    valid = make_metrics()
    assert valid.run_id == "run-test-1"
    assert valid.operation == OperationType.GENERATION

    for invalid in (
        {"run_id": ""},
        {"presentation_id": " "},
        {"latency_ms": -0.1},
        {"llm_calls": -1},
        {"estimated_cost_usd": -0.01},
        {"affected_slide_ids": ["slide-1", "slide-1"]},
    ):
        try:
            make_metrics(**invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Invalid metrics data was accepted: {invalid}")

    generated_directory = Path(__file__).parent / "generated"
    generated_directory.mkdir(parents=True, exist_ok=True)
    jsonl_path = generated_directory / f"metrics_test_{uuid4().hex}.jsonl"
    store = MetricsStore(jsonl_path)
    collector = RunMetricsCollector(
        operation=OperationType.SELECTIVE_REGENERATION,
        presentation_id="presentation-selective-test",
        modification_request="Change slide 3.",
        model_name="gemini-test-model",
        store=store,
    )
    collector.record_llm_call("gemini-test-model")
    collector.record_gemini_usage(120, 40, 165, usage_available=True)
    collector.record_llm_call("gemini-test-model")
    collector.record_gemini_usage(None, None, None, usage_available=False)
    collector.record_validation_error()
    collector.set_slide_counts(1, 5, ["slide-3"])
    time.sleep(0.002)
    saved = collector.finish("success")

    assert saved.latency_ms > 0
    assert saved.llm_calls == 2
    assert saved.input_tokens == 120
    assert saved.output_tokens == 40
    assert saved.total_tokens == 165
    assert saved.token_usage_available is False
    assert saved.usage_unavailable_calls == 1
    assert saved.regenerated_slide_count == 1
    assert saved.total_slide_count == 5
    assert saved.validation_errors == 1
    assert saved.affected_slide_ids == ["slide-3"]
    assert jsonl_path.is_file()
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 1
    loaded = store.load_all()
    assert loaded == [saved]
    jsonl_path.unlink()

    cost = calculate_estimated_cost(
        input_tokens=500_000,
        output_tokens=250_000,
        input_price_per_1m=4.0,
        output_price_per_1m=8.0,
    )
    assert cost == 4.0
    assert calculate_estimated_cost(100, 50) == 0.0

    print("RunMetrics validation passed.")
    print("LLM call counting, token aggregation, latency, and slide counts passed.")
    print("Estimated cost calculation passed.")
    print("JSONL persistence and record loading passed.")


if __name__ == "__main__":
    main()
