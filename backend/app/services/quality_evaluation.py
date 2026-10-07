"""Prepare blinded human ratings and summarize entered quality scores.

No model is used to score presentations. Evaluators fill the CSV template and
the summary utility validates those scores before aggregating them.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median, stdev
from typing import Any, Iterable
from uuid import uuid4

from pydantic import ValidationError

from app.models.quality import (
    BlindedLabel,
    QualityDimension,
    QualityEvaluationCase,
    QualityEvaluationMapping,
    QualityRating,
    RegenerationMethod,
)


BACKEND_DIR = Path(__file__).resolve().parents[2]
RESULTS_DIR = BACKEND_DIR / "experiments" / "results"
EXPERIMENT_RESULTS_PATH = RESULTS_DIR / "experiment_results.jsonl"
EXPERIMENT_CASES_PATH = BACKEND_DIR / "experiments" / "experiment_cases.json"
EVALUATION_CASES_PATH = RESULTS_DIR / "quality_evaluation_cases.json"
MAPPING_PATH = RESULTS_DIR / "quality_evaluation_mapping.json"
RATINGS_TEMPLATE_PATH = RESULTS_DIR / "quality_ratings_template.csv"
EVALUATOR_PACKET_PATH = RESULTS_DIR / "quality_evaluator_packet.json"
QUALITY_SUMMARY_PATH = RESULTS_DIR / "quality_summary.json"
BLINDED_PRESENTATIONS_DIR = RESULTS_DIR / "quality_presentations"

RATING_COLUMNS = [
    "evaluation_id",
    "blinded_label",
    "relevance",
    "completeness",
    "consistency",
    "readability",
    "layout_suitability",
    "requirement_adherence",
    "evaluator_id",
    "optional_comments",
]
SCORE_DIMENSIONS = [dimension.value for dimension in QualityDimension]


def _new_evaluation_id() -> str:
    """Create an opaque random identifier that does not encode the method."""
    return f"eval-{uuid4().hex[:20]}"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid experiment JSONL line {line_number}: {exc}") from exc
    return records


def _localized_case_ids(config_path: Path) -> set[str]:
    config = _load_json(config_path)
    localized: set[str] = set()
    for presentation_case in config.get("presentation_cases", []):
        for modification in presentation_case.get("modifications", []):
            if modification.get("kind") in {"localized_content", "localized_structural_content"}:
                localized.add(modification["case_id"])
    if len(localized) != 10:
        raise ValueError(
            f"Expected ten localized modification cases in the experiment config; found {len(localized)}."
        )
    return localized


def _complete_pairs(
    records: list[dict[str, Any]],
    localized_case_ids: set[str],
    requested_experiment_id: str | None = None,
) -> list[tuple[str, str, dict[str, dict[str, Any]]]]:
    """Return complete, successful localized pairs by experiment and case."""
    experiments: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    order: list[str] = []
    for record in records:
        experiment_id = record.get("experiment_id")
        case_id = record.get("case_id")
        method = record.get("method")
        if not experiment_id or case_id not in localized_case_ids or method not in {"selective", "full"}:
            continue
        if experiment_id not in experiments:
            experiments[experiment_id] = defaultdict(dict)
            order.append(experiment_id)
        experiments[experiment_id][case_id][method] = record

    for candidate_experiment_id in reversed(order):
        if (
            requested_experiment_id is not None
            and candidate_experiment_id != requested_experiment_id
        ):
            continue
        pairs: list[tuple[str, str, dict[str, dict[str, Any]]]] = []
        for case_id in sorted(localized_case_ids):
            methods = experiments[candidate_experiment_id].get(case_id, {})
            if set(methods) != {"selective", "full"}:
                break
            selective = methods["selective"]
            full = methods["full"]
            if selective.get("status") != "regenerated" or full.get("status") != "regenerated":
                break
            if not selective.get("output_path") or not full.get("output_path"):
                break
            if not Path(selective["output_path"]).is_file() or not Path(full["output_path"]).is_file():
                break
            if selective.get("presentation_id") != full.get("presentation_id"):
                raise ValueError(f"Methods do not share the original presentation for {case_id}.")
            if selective.get("modification_request") != full.get("modification_request"):
                raise ValueError(f"Methods do not share the modification request for {case_id}.")
            pairs.append((candidate_experiment_id, case_id, methods))
        if len(pairs) == 10:
            return pairs
    raise ValueError("No complete experiment with all ten successful localized pairs was found.")


def _copy_without_overwrite(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Evaluation presentation does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
            raise FileExistsError(f"Refusing to replace existing blinded evaluation file: {target}")
        return
    shutil.copy2(source, target)


def _package_from_results(
    experiment_results_path: Path,
    experiment_cases_path: Path,
    *,
    experiment_id: str | None = None,
    blinded_dir: Path,
) -> tuple[str, list[QualityEvaluationCase], list[QualityEvaluationMapping], list[dict[str, Any]]]:
    """Make a 20-deck package from the newest complete run's ten local pairs."""
    localized_ids = _localized_case_ids(experiment_cases_path)
    records = _load_jsonl(experiment_results_path)
    pairs = _complete_pairs(records, localized_ids, requested_experiment_id=experiment_id)
    if experiment_id is not None:
        if len(pairs) != 10:
            raise ValueError(f"Experiment {experiment_id} does not have ten complete localized pairs.")
    selected_experiment_id = pairs[0][0]

    label_randomizer = random.SystemRandom()
    cases: list[QualityEvaluationCase] = []
    mappings: list[QualityEvaluationMapping] = []
    evaluator_packet: list[dict[str, Any]] = []

    for pair_experiment_id, case_id, methods in pairs:
        selective = methods["selective"]
        full = methods["full"]
        if pair_experiment_id != selected_experiment_id:
            raise ValueError("A quality dataset cannot mix different experiment runs.")
        labels = [BlindedLabel.VERSION_A, BlindedLabel.VERSION_B]
        label_randomizer.shuffle(labels)
        original_id = selective["presentation_id"]
        original_path = BACKEND_DIR / "generated" / f"presentation_{original_id}_v1.pptx"
        pair_records = {"selective": selective, "full": full}
        presentation_case_id = selective.get("presentation_case_id", "")
        request = selective["modification_request"]
        original_blind_path = blinded_dir / f"{presentation_case_id}_original.pptx"
        _copy_without_overwrite(original_path, original_blind_path)

        for method_name in ("selective", "full"):
            result = pair_records[method_name]
            method = RegenerationMethod(method_name)
            eval_id = _new_evaluation_id()
            label = labels[0] if method == RegenerationMethod.SELECTIVE else labels[1]
            blinded_path = blinded_dir / f"{eval_id}_{label.value.lower().replace(' ', '-')}.pptx"
            _copy_without_overwrite(Path(result["output_path"]), blinded_path)
            cases.append(
                QualityEvaluationCase(
                    evaluation_id=eval_id,
                    experiment_id=selected_experiment_id,
                    case_id=case_id,
                    presentation_case_id=presentation_case_id,
                    modification_request=request,
                    method=method,
                    original_presentation_id=original_id,
                    output_pptx_path=str(Path(result["output_path"]).resolve()),
                    affected_slide_ids=result.get("affected_slide_ids", []),
                    quality_status="pending",
                    blinded_pptx_path=str(blinded_path.resolve()),
                    original_pptx_path=str(original_blind_path.resolve()),
                )
            )
            mappings.append(
                QualityEvaluationMapping(
                    evaluation_id=eval_id,
                    blinded_label=label,
                    actual_method=method,
                )
            )
            evaluator_packet.append(
                {
                    "evaluation_id": eval_id,
                    "blinded_label": label.value,
                    "case_id": case_id,
                    "presentation_case_id": presentation_case_id,
                    "modification_request": request,
                    "original_presentation_path": str(original_blind_path.resolve()),
                    "output_pptx_path": str(blinded_path.resolve()),
                }
            )

    validate_evaluation_package(cases, mappings, localized_ids)
    return selected_experiment_id, cases, mappings, evaluator_packet


def validate_evaluation_package(
    cases: Iterable[QualityEvaluationCase | dict[str, Any]],
    mappings: Iterable[QualityEvaluationMapping | dict[str, Any]],
    localized_case_ids: set[str],
) -> tuple[list[QualityEvaluationCase], list[QualityEvaluationMapping]]:
    """Validate localized scope and one-to-one blinded method assignments."""
    validated_cases = [QualityEvaluationCase.model_validate(case) for case in cases]
    validated_mappings = [QualityEvaluationMapping.model_validate(item) for item in mappings]
    case_by_id = {case.evaluation_id: case for case in validated_cases}
    if len(case_by_id) != len(validated_cases):
        raise ValueError("Evaluation IDs must be unique.")
    mapping_by_id = {item.evaluation_id: item for item in validated_mappings}
    if len(mapping_by_id) != len(validated_mappings):
        raise ValueError("Every evaluation ID must have exactly one mapping.")
    if set(case_by_id) != set(mapping_by_id):
        raise ValueError("Every evaluation case must have exactly one method mapping.")

    by_case: dict[str, list[QualityEvaluationCase]] = defaultdict(list)
    for case in validated_cases:
        if case.case_id not in localized_case_ids:
            raise ValueError(f"Global or unknown case {case.case_id} is not eligible for quality evaluation.")
        if mapping_by_id[case.evaluation_id].actual_method != case.method:
            raise ValueError(f"Method mapping does not match evaluation case {case.evaluation_id}.")
        by_case[case.case_id].append(case)
    for case_id, pair in by_case.items():
        if len(pair) != 2 or {item.method for item in pair} != set(RegenerationMethod):
            raise ValueError(f"Case {case_id} must contain one selective and one full evaluation.")
        labels = {mapping_by_id[item.evaluation_id].blinded_label for item in pair}
        if labels != set(BlindedLabel):
            raise ValueError(f"Case {case_id} must map the two methods to different blinded labels.")
    return validated_cases, validated_mappings


def validate_ratings(
    ratings: Iterable[QualityRating | dict[str, Any]],
    cases: Iterable[QualityEvaluationCase | dict[str, Any]],
    mappings: Iterable[QualityEvaluationMapping | dict[str, Any]],
) -> list[QualityRating]:
    """Validate human scores, references, blind labels, and evaluator duplicates."""
    validated_cases = [QualityEvaluationCase.model_validate(case) for case in cases]
    validated_mappings = [QualityEvaluationMapping.model_validate(item) for item in mappings]
    case_ids = {case.evaluation_id for case in validated_cases}
    mapping_by_id = {mapping.evaluation_id: mapping for mapping in validated_mappings}
    if len(mapping_by_id) != len(validated_mappings):
        raise ValueError("Every evaluation ID must have exactly one method mapping.")
    if case_ids != set(mapping_by_id):
        raise ValueError("Every evaluation case must have a method mapping before ratings are loaded.")
    validated_ratings = [QualityRating.model_validate(rating) for rating in ratings]
    seen: set[tuple[str, str]] = set()
    for rating in validated_ratings:
        if rating.evaluation_id not in case_ids:
            raise ValueError(f"Unknown evaluation_id: {rating.evaluation_id}")
        if mapping_by_id[rating.evaluation_id].blinded_label != rating.blinded_label:
            raise ValueError(f"Blinded label does not match evaluation_id {rating.evaluation_id}.")
        duplicate_key = (rating.evaluator_id, rating.evaluation_id)
        if duplicate_key in seen:
            raise ValueError(
                f"Duplicate rating for evaluator {rating.evaluator_id} and evaluation {rating.evaluation_id}."
            )
        seen.add(duplicate_key)
    if validated_cases and {item.actual_method for item in validated_mappings} != set(RegenerationMethod):
        raise ValueError("The evaluation package must represent both regeneration methods.")
    return validated_ratings


def read_ratings_csv(
    ratings_path: Path,
    cases: Iterable[QualityEvaluationCase | dict[str, Any]],
    mappings: Iterable[QualityEvaluationMapping | dict[str, Any]],
) -> list[QualityRating]:
    """Read completed CSV rows; reject partial or malformed ratings."""
    if not ratings_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with ratings_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != RATING_COLUMNS:
            raise ValueError("Ratings CSV columns do not match the required evaluation template.")
        for line_number, row in enumerate(reader, start=2):
            values = {key: (value or "").strip() for key, value in row.items()}
            if all(not values.get(key) for key in SCORE_DIMENSIONS) and not values.get("evaluator_id"):
                if values.get("optional_comments"):
                    raise ValueError(f"Ratings CSV line {line_number} has comments but no rating.")
                continue
            for dimension in SCORE_DIMENSIONS:
                score = values.get(dimension, "")
                if not score or not score.isdecimal():
                    raise ValueError(
                        f"Ratings CSV line {line_number}: {dimension} must be an integer from 1 to 5."
                    )
                values[dimension] = int(score)
            try:
                rows.append(QualityRating.model_validate(values))
            except ValidationError as exc:
                raise ValueError(f"Invalid human rating on CSV line {line_number}: {exc}") from exc
    return validate_ratings(rows, cases, mappings)


def _empty_method_metrics() -> dict[str, Any]:
    return {
        "rating_count": 0,
        "average_relevance": None,
        "average_completeness": None,
        "average_consistency": None,
        "average_readability": None,
        "average_layout_suitability": None,
        "average_requirement_adherence": None,
        "overall_average_quality_score": None,
        "median_overall_quality": None,
        "standard_deviation_overall_quality": None,
    }


def _aggregate_method(ratings: list[QualityRating]) -> dict[str, Any]:
    if not ratings:
        return _empty_method_metrics()
    overall_scores = [rating.overall_score() for rating in ratings]
    result: dict[str, Any] = {"rating_count": len(ratings)}
    for dimension in QualityDimension:
        result[f"average_{dimension.value}"] = fmean(
            getattr(rating, dimension.value) for rating in ratings
        )
    result["overall_average_quality_score"] = fmean(overall_scores)
    result["median_overall_quality"] = median(overall_scores)
    result["standard_deviation_overall_quality"] = (
        stdev(overall_scores) if len(overall_scores) >= 2 else None
    )
    return result


def build_quality_summary(
    experiment_id: str,
    cases: Iterable[QualityEvaluationCase | dict[str, Any]],
    mappings: Iterable[QualityEvaluationMapping | dict[str, Any]],
    ratings: Iterable[QualityRating | dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate actual ratings only; missing scores remain null."""
    validated_cases = [QualityEvaluationCase.model_validate(case) for case in cases]
    validated_mappings = [QualityEvaluationMapping.model_validate(item) for item in mappings]
    validated_ratings = validate_ratings(ratings, validated_cases, validated_mappings)
    method_by_id = {item.evaluation_id: item.actual_method for item in validated_mappings}
    ratings_by_method: dict[RegenerationMethod, list[QualityRating]] = defaultdict(list)
    for rating in validated_ratings:
        ratings_by_method[method_by_id[rating.evaluation_id]].append(rating)

    selective_metrics = _aggregate_method(ratings_by_method[RegenerationMethod.SELECTIVE])
    full_metrics = _aggregate_method(ratings_by_method[RegenerationMethod.FULL])
    difference: dict[str, Any] = {
        "selective_minus_full": None,
        "absolute_difference": None,
        "within_0_5_observed_difference": None,
        "dimension_differences": {},
    }
    selective_average = selective_metrics["overall_average_quality_score"]
    full_average = full_metrics["overall_average_quality_score"]
    if selective_average is not None and full_average is not None:
        signed_difference = selective_average - full_average
        difference.update(
            {
                "selective_minus_full": signed_difference,
                "absolute_difference": abs(signed_difference),
                "within_0_5_observed_difference": abs(signed_difference) <= 0.5,
                "interpretation": (
                    "within a 0.5-point observed difference"
                    if abs(signed_difference) <= 0.5
                    else "observed difference greater than 0.5 points"
                ),
            }
        )
    for dimension in QualityDimension:
        selective_value = selective_metrics[f"average_{dimension.value}"]
        full_value = full_metrics[f"average_{dimension.value}"]
        signed = (
            selective_value - full_value
            if selective_value is not None and full_value is not None
            else None
        )
        difference["dimension_differences"][dimension.value] = {
            "selective_minus_full": signed,
            "absolute_difference": abs(signed) if signed is not None else None,
        }

    rated_ids = {rating.evaluation_id for rating in validated_ratings}
    evaluator_ids = {rating.evaluator_id for rating in validated_ratings}
    evaluated_cases = len(rated_ids)
    status = (
        "pending_human_ratings"
        if evaluated_cases == 0
        else "complete"
        if evaluated_cases == len(validated_cases)
        else "in_progress"
    )
    return {
        "experiment_id": experiment_id,
        "number_of_cases": len({case.case_id for case in validated_cases}),
        "number_of_prepared_presentations": len(validated_cases),
        "number_of_evaluated_presentations": evaluated_cases,
        "number_of_evaluators": len(evaluator_ids),
        "selective_metrics": selective_metrics,
        "full_metrics": full_metrics,
        "quality_difference": difference,
        "evaluation_status": status,
        "ratings_are_human_entered": True,
        "statistical_significance_tested": False,
    }


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def _write_ratings_template(
    path: Path,
    cases: list[QualityEvaluationCase],
    mappings: list[QualityEvaluationMapping],
) -> None:
    labels = {mapping.evaluation_id: mapping.blinded_label.value for mapping in mappings}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=RATING_COLUMNS)
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "evaluation_id": case.evaluation_id,
                    "blinded_label": labels[case.evaluation_id],
                    **{dimension: "" for dimension in SCORE_DIMENSIONS},
                    "evaluator_id": "",
                    "optional_comments": "",
                }
            )


def prepare_quality_evaluation(
    *,
    experiment_results_path: Path = EXPERIMENT_RESULTS_PATH,
    experiment_cases_path: Path = EXPERIMENT_CASES_PATH,
    output_dir: Path = RESULTS_DIR,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    """Create the localized-case dataset, stable blind mapping, and empty summary."""
    case_path = output_dir / "quality_evaluation_cases.json"
    mapping_path = output_dir / "quality_evaluation_mapping.json"
    packet_path = output_dir / "quality_evaluator_packet.json"
    template_path = output_dir / "quality_ratings_template.csv"
    summary_path = output_dir / "quality_summary.json"
    blinded_dir = output_dir / "quality_presentations"

    if case_path.exists() != mapping_path.exists():
        raise FileExistsError(
            "Evaluation cases and blinded mapping must be kept together; refusing to recreate either one."
        )
    if case_path.exists():
        case_payload = _load_json(case_path)
        mapping_payload = _load_json(mapping_path)
        active_experiment_id = case_payload["experiment_id"]
        cases, mappings = validate_evaluation_package(
            case_payload["cases"],
            mapping_payload["mappings"],
            _localized_case_ids(experiment_cases_path),
        )
    else:
        active_experiment_id, cases, mappings, packet = _package_from_results(
            experiment_results_path,
            experiment_cases_path,
            experiment_id=experiment_id,
            blinded_dir=blinded_dir,
        )
        _write_json(
            case_path,
            {"experiment_id": active_experiment_id, "cases": [case.model_dump(mode="json") for case in cases]},
        )
        _write_json(
            mapping_path,
            {
                "experiment_id": active_experiment_id,
                "mappings": [mapping.model_dump(mode="json") for mapping in mappings],
            },
        )
        _write_json(packet_path, {"experiment_id": active_experiment_id, "presentations": packet})

    if not packet_path.exists():
        label_by_id = {mapping.evaluation_id: mapping.blinded_label.value for mapping in mappings}
        _write_json(
            packet_path,
            {
                "experiment_id": active_experiment_id,
                "presentations": [
                    {
                        "evaluation_id": case.evaluation_id,
                        "blinded_label": label_by_id[case.evaluation_id],
                        "case_id": case.case_id,
                        "presentation_case_id": case.presentation_case_id,
                        "modification_request": case.modification_request,
                        "original_presentation_path": case.original_pptx_path,
                        "output_pptx_path": case.blinded_pptx_path,
                    }
                    for case in cases
                ],
            },
        )

    if not template_path.exists():
        _write_ratings_template(template_path, cases, mappings)
    ratings = read_ratings_csv(template_path, cases, mappings)
    summary = build_quality_summary(active_experiment_id, cases, mappings, ratings)
    _write_json(summary_path, summary)
    return summary


def update_quality_summary(
    *,
    output_dir: Path = RESULTS_DIR,
    experiment_cases_path: Path = EXPERIMENT_CASES_PATH,
) -> dict[str, Any]:
    """Revalidate the CSV and update the derived quality summary."""
    case_payload = _load_json(output_dir / "quality_evaluation_cases.json")
    mapping_payload = _load_json(output_dir / "quality_evaluation_mapping.json")
    cases, mappings = validate_evaluation_package(
        case_payload["cases"],
        mapping_payload["mappings"],
        _localized_case_ids(experiment_cases_path),
    )
    ratings = read_ratings_csv(output_dir / "quality_ratings_template.csv", cases, mappings)
    summary = build_quality_summary(case_payload["experiment_id"], cases, mappings, ratings)
    _write_json(output_dir / "quality_summary.json", summary)
    return summary


if __name__ == "__main__":
    summary = prepare_quality_evaluation()
    print(
        f"Quality evaluation package: {summary['number_of_cases']} cases, "
        f"{summary['number_of_prepared_presentations']} blinded presentations, "
        f"status={summary['evaluation_status']}"
    )
