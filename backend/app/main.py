"""Minimal FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.generation import router as generation_router

app = FastAPI(title="AI PowerPoint Generator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(generation_router, prefix="/api", tags=["generation"])


@app.get("/health")
def health_check() -> dict[str, str]:
    """Report that the backend is running."""
    return {"status": "ok"}
