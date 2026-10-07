"""Versioned local JSON persistence for validated presentations."""

import json
import re
from pathlib import Path

from app.models.presentation import Presentation


class PresentationStore:
    """Store generated presentation versions under backend/generated."""

    def __init__(self, directory: str | Path | None = None) -> None:
        self.directory = (
            Path(directory)
            if directory is not None
            else Path(__file__).resolve().parents[2] / "generated"
        )

    @staticmethod
    def _validate_id(presentation_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", presentation_id):
            raise ValueError("Presentation ID contains unsupported filename characters.")
        return presentation_id

    def next_version(self, presentation_id: str) -> int:
        presentation_id = self._validate_id(presentation_id)
        versions = [
            int(match.group(1))
            for path in self.directory.glob(f"presentation_{presentation_id}_v*.json")
            if (match := re.fullmatch(
                rf"presentation_{re.escape(presentation_id)}_v(\d+)\.json", path.name
            ))
        ]
        return max(versions, default=0) + 1

    def save(self, presentation: Presentation, version: int | None = None) -> Path:
        presentation = Presentation.model_validate(presentation)
        self._validate_id(presentation.id)
        selected_version = version if version is not None else self.next_version(presentation.id)
        if selected_version < 1:
            raise ValueError("Presentation version must be a positive integer.")
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"presentation_{presentation.id}_v{selected_version}.json"
        path.write_text(presentation.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_latest(self, presentation_id: str) -> tuple[Presentation, int]:
        presentation_id = self._validate_id(presentation_id)
        version = self.next_version(presentation_id) - 1
        if version < 1:
            raise FileNotFoundError(f"No stored presentation found for ID '{presentation_id}'.")
        path = self.directory / f"presentation_{presentation_id}_v{version}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            presentation = Presentation.model_validate(data)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Stored presentation version {version} is invalid: {exc}") from exc
        if presentation.id != presentation_id:
            raise ValueError("Stored presentation ID does not match its filename.")
        return presentation, version
