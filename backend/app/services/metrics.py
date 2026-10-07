"""Small JSONL metrics collector for generation and modification operations."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.llm.provider import LLMCallUsage
from app.models.metrics import OperationType, RunMetrics


# Configure these values when pricing for the selected model/account is known.
INPUT_PRICE_PER_1M_TOKENS = 0.0
OUTPUT_PRICE_PER_1M_TOKENS = 0.0


def calculate_estimated_cost(
    input_tokens: int,
    output_tokens: int,
    input_price_per_1m: float = INPUT_PRICE_PER_1M_TOKENS,
    output_price_per_1m: float = OUTPUT_PRICE_PER_1M_TOKENS,
) -> float:
    """Calculate an estimate using configured per-million-token prices."""
    values = (input_tokens, output_tokens, input_price_per_1m, output_price_per_1m)
    if any(value < 0 for value in values):
        raise ValueError("Token counts and token prices must be non-negative.")
    return (
        input_tokens / 1_000_000 * input_price_per_1m
        + output_tokens / 1_000_000 * output_price_per_1m
    )


class MetricsStore:
    """Append and load newline-delimited JSON metrics records."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = (
            Path(path)
            if path is not None
            else Path(__file__).resolve().parents[2] / "generated" / "metrics.jsonl"
        )

    def append(self, metrics: RunMetrics) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(metrics.model_dump_json() + "\n")

    def load_all(self) -> list[RunMetrics]:
        if not self.path.exists():
            return []
        records = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip():
                try:
                    records.append(RunMetrics.model_validate_json(line))
                except ValueError as exc:
                    raise ValueError(f"Invalid metrics record on JSONL line {line_number}: {exc}") from exc
        return records


class RunMetricsCollector:
    """Accumulate one run and persist it when the operation returns."""

    def __init__(
        self,
        operation: OperationType,
        presentation_id: str,
        modification_request: str | None = None,
        model_name: str | None = None,
        store: MetricsStore | None = None,
    ) -> None:
        self.run_id = f"run-{uuid4().hex}"
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.operation = operation
        self.presentation_id = presentation_id
        self.modification_request = modification_request
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        self._store = store or MetricsStore()
        self._started = time.perf_counter()
        self._input_tokens = 0
        self._output_tokens = 0
        self._total_tokens = 0
        self._llm_calls = 0
        self._usage_unavailable_calls = 0
        self._validation_errors = 0
        self._regenerated_slide_count = 0
        self._total_slide_count = 0
        self._affected_slide_ids: list[str] = []

    def record_llm_call(self, model_name: str) -> None:
        """Count one actual provider/API call."""
        self._llm_calls += 1
        self.model_name = model_name

    def record_gemini_usage(
        self,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        usage_available: bool,
    ) -> None:
        """Accumulate actual SDK token fields; missing values contribute zero."""
        if any(value is not None and value < 0 for value in (input_tokens, output_tokens, total_tokens)):
            raise ValueError("Gemini token usage values must be non-negative.")
        self._input_tokens += input_tokens or 0
        self._output_tokens += output_tokens or 0
        self._total_tokens += total_tokens or 0
        if not usage_available:
            self._usage_unavailable_calls += 1

    def record_provider_calls(self, calls: list[LLMCallUsage]) -> None:
        """Import all call records collected by the provider for this run."""
        for call in calls:
            self.record_llm_call(call.model_name)
            self.record_gemini_usage(
                call.input_tokens,
                call.output_tokens,
                call.total_tokens,
                call.usage_available,
            )

    def record_validation_error(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("Validation error count must be non-negative.")
        self._validation_errors += count

    def set_slide_counts(
        self,
        regenerated_slide_count: int,
        total_slide_count: int,
        affected_slide_ids: list[str] | None = None,
    ) -> None:
        if regenerated_slide_count < 0 or total_slide_count < 0:
            raise ValueError("Slide counts must be non-negative.")
        if affected_slide_ids and len(affected_slide_ids) != len(set(affected_slide_ids)):
            raise ValueError("Affected slide IDs must not contain duplicates.")
        self._regenerated_slide_count = regenerated_slide_count
        self._total_slide_count = total_slide_count
        self._affected_slide_ids = list(affected_slide_ids or [])

    def finish(self, status: str) -> RunMetrics:
        """Stop the monotonic timer, persist, and return the final record."""
        latency_ms = (time.perf_counter() - self._started) * 1000
        metrics = RunMetrics(
            run_id=self.run_id,
            timestamp=self.timestamp,
            operation=self.operation,
            presentation_id=self.presentation_id,
            modification_request=self.modification_request,
            status=status,
            model_name=self.model_name,
            latency_ms=latency_ms,
            llm_calls=self._llm_calls,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            total_tokens=self._total_tokens,
            token_usage_available=(self._llm_calls > 0 and self._usage_unavailable_calls == 0),
            usage_unavailable_calls=self._usage_unavailable_calls,
            regenerated_slide_count=self._regenerated_slide_count,
            total_slide_count=self._total_slide_count,
            validation_errors=self._validation_errors,
            estimated_cost_usd=calculate_estimated_cost(self._input_tokens, self._output_tokens),
            affected_slide_ids=self._affected_slide_ids,
        )
        self._store.append(metrics)
        return metrics


def load_metrics(path: str | Path | None = None) -> list[RunMetrics]:
    """Convenience reader for existing JSONL records."""
    return MetricsStore(path).load_all()
