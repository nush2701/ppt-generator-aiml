"""Run the paired selective-versus-full regeneration MVP experiment.

Run from the backend directory with: python run_experiment.py
The script uses the configured Gemini API and appends one result per method/run.
"""

from __future__ import annotations

import json
import argparse
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.llm.gemini_provider import GeminiProvider
from app.models.full_regeneration import FullRegenerationStatus
from app.models.metrics import OperationType, RunMetrics
from app.models.presentation import Presentation
from app.models.requirements import PresentationRequirements
from app.models.selective_regeneration import SelectiveRegenerationStatus
from app.services.full_regenerator import FullRegenerator
from app.services.metrics import RunMetricsCollector
from app.services.presentation_generator import PresentationGenerator
from app.services.presentation_store import PresentationStore
from app.services.selective_regenerator import SelectiveRegenerator


BACKEND_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = BACKEND_DIR / "experiments"
RESULTS_DIR = EXPERIMENTS_DIR / "results"
CASES_PATH = EXPERIMENTS_DIR / "experiment_cases.json"
RESULTS_PATH = RESULTS_DIR / "experiment_results.jsonl"
SUMMARY_PATH = RESULTS_DIR / "experiment_summary.json"


def _load_cases() -> list[dict[str, Any]]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    presentations = cases.get("presentation_cases")
    if not isinstance(presentations, list) or len(presentations) != 5:
        raise ValueError("The MVP experiment configuration must contain exactly five presentations.")
    for presentation in presentations:
        if not presentation.get("case_id") or not presentation.get("prompt"):
            raise ValueError("Every presentation case needs a case_id and prompt.")
        modifications = presentation.get("modifications")
        if not isinstance(modifications, list) or len(modifications) != 3:
            raise ValueError(
                f"Presentation case {presentation.get('case_id')} must contain exactly three modifications."
            )
        if len({item.get("case_id") for item in modifications}) != 3:
            raise ValueError(f"Modification case IDs must be unique for {presentation['case_id']}.")
        kinds = [item.get("kind") for item in modifications]
        if sorted(kinds) != sorted(
            ["localized_content", "localized_structural_content", "global"]
        ):
            raise ValueError(
                f"{presentation['case_id']} needs one localized, one localized structural, "
                "and one global modification."
            )
    return presentations


def _requirements_from_presentation(presentation: Presentation) -> PresentationRequirements:
    """Restore the generation requirements from the saved original's metadata."""
    metadata = presentation.metadata.root
    return PresentationRequirements.model_validate(
        {
            "topic": metadata.get("topic") or presentation.title,
            "purpose": metadata.get("purpose"),
            "audience": metadata.get("audience"),
            "slide_count": metadata.get("slide_count") or len(presentation.slides),
            "tone": metadata.get("tone"),
            "language": metadata.get("language"),
            "key_requirements": metadata.get("key_requirements") or [],
            "constraints": metadata.get("constraints") or [],
        }
    )


def _append_result(record: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()


def _record_method(
    *,
    experiment_id: str,
    experiment_timestamp: str,
    presentation_case_id: str,
    modification_case: dict[str, str],
    presentation: Presentation,
    requirements: PresentationRequirements,
    method: str,
) -> dict[str, Any]:
    request = modification_case["prompt"]
    operation = (
        OperationType.SELECTIVE_REGENERATION
        if method == "selective"
        else OperationType.FULL_REGENERATION
    )
    collector = RunMetricsCollector(
        operation=operation,
        presentation_id=presentation.id,
        modification_request=request,
    )
    provider: GeminiProvider | None = None
    status = "failed"
    regenerated_ids: list[str] = []
    affected_ids: list[str] = []
    validation_errors = 0
    message: str | None = None
    output_path: str | None = None

    try:
        provider = GeminiProvider()
        collector.model_name = provider.model
        # Each strategy receives a deep copy of the exact same stored original.
        starting_presentation = Presentation.model_validate(presentation.model_dump(mode="python"))
        if method == "selective":
            result = SelectiveRegenerator(provider).selectively_regenerate(
                starting_presentation,
                requirements.model_copy(deep=True),
                request,
            )
            status = result.status.value
            regenerated_ids = list(result.regenerated_slides)
            affected_ids = list(result.affected_slides)
            message = result.message
            output_path = str(result.output_path) if result.output_path else None
            if result.status == SelectiveRegenerationStatus.REGENERATED:
                validation_errors = 0
        else:
            result = FullRegenerator(provider).fully_regenerate(
                starting_presentation,
                requirements.model_copy(deep=True),
                request,
            )
            status = result.status.value
            regenerated_ids = list(result.regenerated_slides)
            affected_ids = list(result.regenerated_slides)
            validation_errors = result.validation_errors
            message = result.message
            output_path = str(result.output_path) if result.output_path else None
            if result.status == FullRegenerationStatus.REGENERATED:
                validation_errors = result.validation_errors
    except Exception as exc:
        # Preserve the failure and continue to the paired method/case.
        message = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, (ValidationError, ValueError)):
            validation_errors = 1
    finally:
        if provider is not None:
            collector.record_provider_calls(provider.usage_records)
        collector.record_validation_error(validation_errors)
        collector.set_slide_counts(
            regenerated_slide_count=len(regenerated_ids),
            total_slide_count=len(presentation.slides),
            affected_slide_ids=affected_ids,
        )
        metrics = collector.finish(status)

    record = _result_record(
        metrics=metrics,
        experiment_id=experiment_id,
        experiment_timestamp=experiment_timestamp,
        presentation_case_id=presentation_case_id,
        modification_case=modification_case,
        method=method,
        message=message,
        output_path=output_path,
    )
    _append_result(record)
    return record


def _result_record(
    *,
    metrics: RunMetrics,
    experiment_id: str,
    experiment_timestamp: str,
    presentation_case_id: str,
    modification_case: dict[str, str],
    method: str,
    message: str | None,
    output_path: str | None,
) -> dict[str, Any]:
    """Project the existing persisted metrics record into experiment data."""
    return {
        "experiment_id": experiment_id,
        "experiment_timestamp": experiment_timestamp,
        "case_id": modification_case["case_id"],
        "presentation_case_id": presentation_case_id,
        "presentation_id": metrics.presentation_id,
        "modification_request": metrics.modification_request,
        "method": method,
        "status": metrics.status,
        "run_id": metrics.run_id,
        "llm_calls": metrics.llm_calls,
        "input_tokens": metrics.input_tokens,
        "output_tokens": metrics.output_tokens,
        "total_tokens": metrics.total_tokens,
        "latency_ms": metrics.latency_ms,
        "regenerated_slide_count": metrics.regenerated_slide_count,
        "total_slide_count": metrics.total_slide_count,
        "validation_errors": metrics.validation_errors,
        "estimated_cost_usd": metrics.estimated_cost_usd,
        "affected_slide_ids": metrics.affected_slide_ids,
        "token_usage_available": metrics.token_usage_available,
        "usage_unavailable_calls": metrics.usage_unavailable_calls,
        "model_name": metrics.model_name,
        "message": message,
        "output_path": output_path,
    }


def _average(records: list[dict[str, Any]], field: str) -> float:
    return statistics.fmean(record[field] for record in records) if records else 0.0


def _median(records: list[dict[str, Any]], field: str) -> float:
    return statistics.median(record[field] for record in records) if records else 0.0


def _method_summary(records: list[dict[str, Any]], method: str) -> dict[str, Any]:
    attempted = [
        record
        for record in records
        if record["method"] == method
    ]
    successful = [record for record in attempted if record["status"] == "regenerated"]
    fields = {
        "average_llm_calls": "llm_calls",
        "average_input_tokens": "input_tokens",
        "average_output_tokens": "output_tokens",
        "average_total_tokens": "total_tokens",
        "average_latency_ms": "latency_ms",
        "average_regenerated_slides": "regenerated_slide_count",
        "average_validation_errors": "validation_errors",
        "average_estimated_cost_usd": "estimated_cost_usd",
    }
    summary: dict[str, Any] = {
        "successful_runs": len(successful),
        "total_runs": len(attempted),
        "failed_or_unhandled_runs": sum(
            record["status"] not in {"regenerated", "global_change", "clarification_needed"}
            for record in attempted
        ),
        "global_change_runs": sum(record["status"] == "global_change" for record in attempted),
        "clarification_needed_runs": sum(
            record["status"] == "clarification_needed" for record in attempted
        ),
    }
    # Means and medians cover every attempted run so failed/clarification calls
    # still contribute their actual analyzer usage and latency.
    summary.update({key: _average(attempted, field) for key, field in fields.items()})
    summary["median_latency_ms"] = _median(attempted, "latency_ms")
    summary["median_total_tokens"] = _median(attempted, "total_tokens")
    return summary


def _build_summary(
    experiment_id: str,
    experiment_timestamp: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    selective = _method_summary(records, "selective")
    baseline = _method_summary(records, "full")
    selective_by_case = {
        record["case_id"]: record
        for record in records
        if record["method"] == "selective" and record["status"] == "regenerated"
    }
    baseline_by_case = {
        record["case_id"]: record
        for record in records
        if record["method"] == "full" and record["status"] == "regenerated"
    }
    paired = [
        (selective_by_case[case_id], baseline_by_case[case_id])
        for case_id in selective_by_case.keys() & baseline_by_case.keys()
    ]
    def reduction(field: str) -> float | None:
        selective_total = sum(local[field] for local, _ in paired)
        baseline_total = sum(full[field] for _, full in paired)
        if baseline_total == 0:
            return None
        return ((baseline_total - selective_total) / baseline_total) * 100

    return {
        "experiment_id": experiment_id,
        "timestamp": experiment_timestamp,
        "paired_case_count": len(paired),
        "selective_regeneration": selective,
        "full_regeneration": baseline,
        "token_reduction_percent": reduction("total_tokens"),
        "latency_reduction_percent": reduction("latency_ms"),
        "call_reduction_percent": reduction("llm_calls"),
        "slide_regeneration_reduction_percent": reduction("regenerated_slide_count"),
        "token_reduction_pair_count": len(paired),
        "note": (
            "Token reduction uses only case pairs where both methods regenerated successfully. "
            "Selective global_change and clarification_needed outcomes are not counted as successes."
        ),
    }


def _write_summary(summary: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    history: dict[str, Any] = {"experiments": []}
    if SUMMARY_PATH.exists():
        history = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    experiments = history.setdefault("experiments", [])
    experiments[:] = [
        previous
        for previous in experiments
        if previous.get("experiment_id") != summary["experiment_id"]
    ]
    experiments.append(summary)
    temporary_path = SUMMARY_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary_path.replace(SUMMARY_PATH)


def run_experiment(limit: int | None = None) -> str:
    if limit is not None and (limit < 1 or limit > 15):
        raise ValueError("--limit must be between 1 and 15 modification cases.")
    experiment_id = f"exp-{uuid4().hex}"
    experiment_timestamp = datetime.now(timezone.utc).isoformat()
    cases = _load_cases()
    store = PresentationStore()
    experiment_records: list[dict[str, Any]] = []

    selected_pairs = [
        (presentation_case, modification_case)
        for presentation_case in cases
        for modification_case in presentation_case["modifications"]
    ]
    if limit is not None:
        selected_pairs = selected_pairs[:limit]
    selected_by_presentation: dict[str, tuple[dict[str, Any], list[dict[str, str]]]] = {}
    for presentation_case, modification_case in selected_pairs:
        selected_by_presentation.setdefault(
            presentation_case["case_id"], (presentation_case, [])
        )[1].append(modification_case)

    for presentation_case, selected_modifications in selected_by_presentation.values():
        case_id = presentation_case["case_id"]
        presentation_id = f"{experiment_id}-{case_id}"
        generation_metrics = RunMetricsCollector(
            operation=OperationType.GENERATION,
            presentation_id=presentation_id,
        )
        generator_provider: GeminiProvider | None = None
        original: Presentation | None = None
        generation_error: str | None = None
        try:
            generator_provider = GeminiProvider()
            generation_metrics.model_name = generator_provider.model
            generated = PresentationGenerator(generator_provider).generate_presentation(
                presentation_case["prompt"],
                presentation_id=presentation_id,
            )
            original, _ = store.load_latest(generated.presentation.id)
        except Exception as exc:
            generation_error = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, (ValidationError, ValueError)):
                generation_metrics.record_validation_error()
        finally:
            if generator_provider is not None:
                generation_metrics.record_provider_calls(generator_provider.usage_records)
            generated_count = len(original.slides) if original is not None else 0
            generation_metrics.set_slide_counts(generated_count, generated_count)
            generation_metrics.finish("generated" if original is not None else "failed")

        if original is None:
            for modification_case in selected_modifications:
                for method in ("selective", "full"):
                    failure_metrics = RunMetricsCollector(
                        operation=(
                            OperationType.SELECTIVE_REGENERATION
                            if method == "selective"
                            else OperationType.FULL_REGENERATION
                        ),
                        presentation_id=presentation_id,
                        modification_request=modification_case["prompt"],
                        model_name=generation_metrics.model_name,
                    ).finish("failed")
                    failed_case = _result_record(
                        metrics=failure_metrics,
                        experiment_id=experiment_id,
                        experiment_timestamp=experiment_timestamp,
                        presentation_case_id=case_id,
                        modification_case=modification_case,
                        method=method,
                        message=f"Original presentation generation failed: {generation_error}",
                        output_path=None,
                    )
                    _append_result(failed_case)
                    experiment_records.append(failed_case)
            continue

        requirements = _requirements_from_presentation(original)
        # Confirm that the just-generated original is available through its persisted store.
        for modification_case in selected_modifications:
            stored_original, _ = store.load_latest(presentation_id)
            # Both strategies receive the same immutable stored state and requirements.
            pair_original = Presentation.model_validate(stored_original.model_dump(mode="python"))
            pair_requirements = requirements.model_copy(deep=True)
            for method in ("selective", "full"):
                record = _record_method(
                    experiment_id=experiment_id,
                    experiment_timestamp=experiment_timestamp,
                    presentation_case_id=case_id,
                    modification_case=modification_case,
                    presentation=pair_original,
                    requirements=pair_requirements,
                    method=method,
                )
                experiment_records.append(record)

    summary = _build_summary(experiment_id, experiment_timestamp, experiment_records)
    _write_summary(summary)
    return experiment_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run paired regeneration experiments.")
    parser.add_argument(
        "--limit",
        type=int,
        help="Run at most this many modification cases (each case runs both methods).",
    )
    args = parser.parse_args()
    completed_experiment_id = run_experiment(limit=args.limit)
    print(f"Experiment complete: {completed_experiment_id}")
    print(f"Results: {RESULTS_PATH}")
    print(f"Summary: {SUMMARY_PATH}")
