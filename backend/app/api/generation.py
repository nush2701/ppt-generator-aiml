"""HTTP endpoint for end-to-end presentation generation."""

from pathlib import Path
import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.llm.gemini_provider import GeminiProvider, GeminiProviderError
from app.models.api import (
    FullModifyPresentationResponse,
    GeneratePresentationRequest,
    GeneratePresentationResponse,
    ModifyPresentationRequest,
    ModifyPresentationResponse,
)
from app.models.requirements import PresentationRequirements
from app.models.full_regeneration import FullRegenerationStatus
from app.models.metrics import OperationType
from app.rendering import PptRenderError
from app.services.presentation_generator import PresentationGenerator
from app.services.presentation_store import PresentationStore
from app.services.full_regenerator import FullRegenerator
from app.services.metrics import RunMetricsCollector
from app.services.selective_regenerator import SelectiveRegenerator


router = APIRouter()

GENERATED_DIR = Path(__file__).resolve().parents[2] / "generated"


def _record_provider_calls(collector: RunMetricsCollector, provider: GeminiProvider | None) -> None:
    if provider is not None:
        collector.record_provider_calls(provider.usage_records)


def _is_provider_validation_error(error: Exception) -> bool:
    message = str(error)
    return (
        "did not match the expected JSON schema" in message
        or "empty or missing structured response" in message
    )


@router.post("/generate", response_model=GeneratePresentationResponse)
def generate(request: GeneratePresentationRequest) -> GeneratePresentationResponse:
    """Generate and render a presentation from the supplied prompt."""
    presentation_id = f"presentation-{uuid4().hex}"
    metrics = RunMetricsCollector(
        operation=OperationType.GENERATION,
        presentation_id=presentation_id,
        model_name=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
    )
    provider = None
    status = "failed"
    try:
        provider = GeminiProvider()
        result = PresentationGenerator(provider).generate_presentation(
            request.prompt,
            presentation_id=presentation_id,
        )
        slide_count = len(result.presentation.slides)
        metrics.set_slide_counts(slide_count, slide_count)
        response = GeneratePresentationResponse(
            run_id=metrics.run_id,
            presentation_id=result.presentation.id,
            title=result.presentation.title,
            slide_count=slide_count,
            file_name=result.output_path.name,
            file_path=str(Path("generated") / result.output_path.name),
        )
        status = "success"
        return response
    except GeminiProviderError as exc:
        if _is_provider_validation_error(exc):
            metrics.record_validation_error()
        message = str(exc)
        status_code = 503 if "GEMINI_API_KEY is missing" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
    except ValidationError as exc:
        metrics.record_validation_error()
        raise HTTPException(
            status_code=502,
            detail=f"Generated presentation data failed validation: {exc}",
        ) from exc
    except PptRenderError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        metrics.record_validation_error()
        raise HTTPException(status_code=502, detail=f"Generation validation failed: {exc}") from exc
    finally:
        _record_provider_calls(metrics, provider)
        metrics.finish(status)


@router.post("/modify", response_model=ModifyPresentationResponse)
def modify(request: ModifyPresentationRequest) -> ModifyPresentationResponse:
    """Apply a slide-level change to a locally persisted presentation."""
    metrics = RunMetricsCollector(
        operation=OperationType.SELECTIVE_REGENERATION,
        presentation_id=request.presentation_id,
        modification_request=request.prompt,
    )
    provider = None
    status = "failed"
    try:
        store = PresentationStore()
        presentation, current_version = store.load_latest(request.presentation_id)
        metrics.set_slide_counts(0, len(presentation.slides))
        requirements = PresentationRequirements.model_validate(presentation.metadata.root)
        next_version = current_version + 1
        generated_dir = GENERATED_DIR
        output_path = generated_dir / f"presentation_{presentation.id}_v{next_version}.pptx"
        provider = GeminiProvider()
        result = SelectiveRegenerator(provider).selectively_regenerate(
            presentation=presentation,
            requirements=requirements,
            modification_request=request.prompt,
            output_path=output_path,
        )
        status = result.status.value
        metrics.set_slide_counts(
            regenerated_slide_count=len(result.regenerated_slides),
            total_slide_count=result.total_slide_count,
            affected_slide_ids=result.affected_slides,
        )
        file_name = None
        file_path = None
        if result.status.value == "regenerated":
            try:
                store.save(result.presentation, version=next_version)
            except OSError as exc:
                status = "failed"
                raise HTTPException(status_code=500, detail=f"Could not persist updated presentation: {exc}") from exc
            file_name = output_path.name
            file_path = str(Path("generated") / file_name)

        return ModifyPresentationResponse(
            run_id=metrics.run_id,
            status=result.status.value,
            title=result.presentation.title,
            presentation_id=result.presentation.id,
            slide_count=result.total_slide_count,
            affected_slides=result.affected_slides,
            regenerated_slides=result.regenerated_slides,
            preserved_slides=result.preserved_slides,
            clarification_needed=result.clarification_needed,
            message=result.message,
            file_name=file_name,
            file_path=file_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GeminiProviderError as exc:
        if _is_provider_validation_error(exc):
            metrics.record_validation_error()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValidationError as exc:
        metrics.record_validation_error()
        raise HTTPException(
            status_code=500,
            detail=f"Stored/generated presentation data failed validation: {exc}",
        ) from exc
    except PptRenderError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        metrics.record_validation_error()
        raise HTTPException(status_code=502, detail=f"Selective regeneration failed: {exc}") from exc
    finally:
        _record_provider_calls(metrics, provider)
        metrics.finish(status)


@router.post("/modify/full", response_model=FullModifyPresentationResponse)
def modify_full(request: ModifyPresentationRequest) -> FullModifyPresentationResponse:
    """Run the full-presentation baseline without changing selective modify."""
    metrics = RunMetricsCollector(
        operation=OperationType.FULL_REGENERATION,
        presentation_id=request.presentation_id,
        modification_request=request.prompt,
    )
    provider = None
    status = "failed"
    try:
        store = PresentationStore()
        presentation, current_version = store.load_latest(request.presentation_id)
        metrics.set_slide_counts(0, len(presentation.slides))
        requirements = PresentationRequirements.model_validate(presentation.metadata.root)
        next_version = current_version + 1
        generated_dir = GENERATED_DIR
        output_path = generated_dir / f"full_regeneration_{uuid4().hex}.pptx"
        provider = GeminiProvider()
        result = FullRegenerator(provider).fully_regenerate(
            presentation=presentation,
            requirements=requirements,
            modification_request=request.prompt,
            output_path=output_path,
        )
        status = result.status.value
        metrics.record_validation_error(result.validation_errors)
        metrics.set_slide_counts(
            regenerated_slide_count=len(result.regenerated_slides),
            total_slide_count=len(result.presentation.slides),
            affected_slide_ids=result.regenerated_slides,
        )

        file_name = None
        file_path = None
        version = None
        if result.status == FullRegenerationStatus.REGENERATED:
            try:
                store.save(result.presentation, version=next_version)
            except OSError as exc:
                status = "failed"
                raise HTTPException(status_code=500, detail=f"Could not persist full-regeneration version: {exc}") from exc
            version = next_version
            file_name = output_path.name
            file_path = str(Path("generated") / file_name)

        return FullModifyPresentationResponse(
            success=result.status == FullRegenerationStatus.REGENERATED,
            run_id=metrics.run_id,
            status=result.status.value,
            title=result.presentation.title,
            presentation_id=result.presentation.id,
            version=version,
            slide_count=len(result.presentation.slides),
            regenerated_slides=result.regenerated_slides,
            message=result.message,
            file_name=file_name,
            file_path=file_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GeminiProviderError as exc:
        if _is_provider_validation_error(exc):
            metrics.record_validation_error()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValidationError as exc:
        metrics.record_validation_error()
        raise HTTPException(status_code=500, detail=f"Presentation data failed validation: {exc}") from exc
    except PptRenderError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        metrics.record_validation_error()
        raise HTTPException(status_code=502, detail=f"Full regeneration failed: {exc}") from exc
    finally:
        _record_provider_calls(metrics, provider)
        metrics.finish(status)


@router.get("/files/{file_name}")
def download_file(file_name: str) -> FileResponse:
    """Serve a generated .pptx from the generated directory."""
    if not file_name.endswith(".pptx") or Path(file_name).name != file_name:
        raise HTTPException(status_code=404, detail="File not found")
    file_path = GENERATED_DIR / file_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=file_name)
