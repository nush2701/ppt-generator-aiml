"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import {
  fileDownloadUrl,
  generatePresentation,
  GenerationResponse,
  modifyPresentation,
  ModifyPresentationResponse,
} from "../lib/api";

function slideLabel(slideId: string): string {
  const match = /^slide-(\d+)$/.exec(slideId);
  return match ? `Slide ${match[1]}` : slideId;
}

function formatSlides(slideIds: string[]): string {
  return slideIds.map(slideLabel).join(", ");
}

function versionLabel(fileName: string): string | null {
  return /_(v\d+)\.pptx$/.exec(fileName)?.[1] ?? null;
}

function selectiveSummary(response: ModifyPresentationResponse): string {
  const regenerated = response.regenerated_slides.map(slideLabel);
  if (regenerated.length === 0) return response.message;
  const subject =
    regenerated.length === 1 ? `${regenerated[0]} was` : `${regenerated.join(", ")} were`;
  const preserved = response.preserved_slides.length;
  if (preserved === 0) return `${subject} regenerated.`;
  return `${subject} regenerated while the remaining ${preserved} slide${
    preserved === 1 ? " was" : "s were"
  } preserved.`;
}

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<GenerationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modification, setModification] = useState("");
  const [isModifying, setIsModifying] = useState(false);
  const [modifyResult, setModifyResult] = useState<ModifyPresentationResponse | null>(null);
  const [lastModifiedResult, setLastModifiedResult] = useState<ModifyPresentationResponse | null>(null);
  const [modifyError, setModifyError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!prompt.trim() || isGenerating || isModifying) return;

    setIsGenerating(true);
    setError(null);
    setResult(null);
    setModifyResult(null);
    setLastModifiedResult(null);
    setModifyError(null);
    try {
      setResult(await generatePresentation(prompt.trim()));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Presentation generation failed. Please try again.",
      );
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleModify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!result || !modification.trim() || isModifying || isGenerating) return;

    setIsModifying(true);
    setModifyError(null);
    try {
      const response = await modifyPresentation(result.presentation_id, modification.trim());
      setModifyResult(response);
      if (response.status === "regenerated" && response.file_name) {
        setLastModifiedResult(response);
      }
    } catch (requestError) {
      setModifyError(
        requestError instanceof Error
          ? requestError.message
          : "Modification failed. Please try again.",
      );
    } finally {
      setIsModifying(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="Storydeck home">
          <span className="brand-mark" aria-hidden="true"><span /></span>
          <span>Storydeck</span>
        </Link>
      </header>

      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">From prompt to presentation</p>
        <h1 id="page-title">AI PowerPoint Generator</h1>
        <p className="hero-copy">
          Turn a natural-language prompt into a structured PowerPoint presentation.
          Describe your topic, audience, and the kind of story you want to tell.
        </p>
      </section>

      <section className="workspace" aria-label="Presentation generator">
        <form className="prompt-card" onSubmit={handleSubmit}>
          <div className="card-heading">
            <div>
              <p className="step-label">YOUR BRIEF <span>01</span></p>
              <h2>What should your presentation cover?</h2>
            </div>
            <div className="document-icon" aria-hidden="true">✳</div>
          </div>

          <label className="sr-only" htmlFor="presentation-prompt">Presentation prompt</label>
          <textarea
            id="presentation-prompt"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Create a 6-slide professional presentation about renewable energy for college students..."
            maxLength={20_000}
            disabled={isGenerating || isModifying}
            required
          />
          <div className="form-footer">
            <span className="input-hint">A few details about your audience and goals help shape the deck.</span>
            <span className="character-count">{prompt.length.toLocaleString()} / 20,000</span>
          </div>
          <button className="generate-button" type="submit" disabled={isGenerating || isModifying || !prompt.trim()}>
            {isGenerating ? (
              <><span className="spinner" aria-hidden="true" /> Generating presentation…</>
            ) : (
              <>Generate presentation <span aria-hidden="true">→</span></>
            )}
          </button>
          {isGenerating && (
            <p className="loading-note" role="status">Building your presentation. This may take a little while.</p>
          )}
        </form>

        {error && (
          <section className="result-card error-card" role="alert">
            <div className="result-icon error-icon" aria-hidden="true">!</div>
            <div><h2>We couldn’t generate your presentation</h2><p>{error}</p></div>
          </section>
        )}

        {result && (
          <section className="result-card success-card" aria-live="polite">
            <div className="result-icon success-icon" aria-hidden="true">✓</div>
            <div className="result-content">
              <p className="success-kicker">Presentation ready</p>
              <h2>{result.title}</h2>
              <div className="result-details">
                <div><span>Slides</span><strong>{result.slide_count}</strong></div>
                {result.run_id && <div><span>Run ID</span><strong>{result.run_id}</strong></div>}
                <div><span>Generated file</span><strong>{result.file_name}</strong></div>
                <div className="file-path"><span>Saved at</span><strong>{result.file_path}</strong></div>
              </div>
              <p className="success-message">Your presentation was generated successfully.</p>
              <a
                className="generate-button"
                href={fileDownloadUrl(result.file_name)}
                download={result.file_name}
              >
                Download PowerPoint <span aria-hidden="true">↓</span>
              </a>
            </div>
          </section>
        )}

        {result && (
          <section className="prompt-card modify-card" aria-labelledby="modify-heading">
            <div className="card-heading">
              <div>
                <p className="step-label">REFINE YOUR DECK <span>02</span></p>
                <h2 id="modify-heading">Modify your presentation</h2>
              </div>
              <div className="document-icon" aria-hidden="true">✎</div>
            </div>
            <form onSubmit={handleModify}>
              <label className="sr-only" htmlFor="modification-prompt">What would you like to change?</label>
              <textarea
                id="modification-prompt"
                value={modification}
                onChange={(event) => setModification(event.target.value)}
                placeholder="Change slide 3 to compare solar and wind energy using clear, concise points."
                maxLength={20_000}
                disabled={isModifying || isGenerating}
              />
              <div className="form-footer">
                <span className="input-hint">
                  Selective regeneration: only the slides that need to change are rebuilt, the rest are preserved.
                </span>
                <span className="character-count">{modification.length.toLocaleString()} / 20,000</span>
              </div>
              <button
                className="generate-button"
                type="submit"
                disabled={isModifying || isGenerating || !modification.trim()}
              >
                {isModifying ? (
                  <><span className="spinner" aria-hidden="true" /> Applying modification…</>
                ) : (
                  <>Apply Modification <span aria-hidden="true">→</span></>
                )}
              </button>
              {isModifying && (
                <p className="loading-note" role="status">Applying your modification. This may take a little while.</p>
              )}
            </form>
          </section>
        )}

        {modifyError && (
          <section className="result-card error-card" role="alert">
            <div className="result-icon error-icon" aria-hidden="true">!</div>
            <div><h2>We couldn’t apply your modification</h2><p>{modifyError}</p></div>
          </section>
        )}

        {lastModifiedResult && lastModifiedResult.file_name && (
          <section className="result-card success-card" aria-live="polite">
            <div className="result-icon success-icon" aria-hidden="true">✓</div>
            <div className="result-content">
              <p className="success-kicker">Modification applied</p>
              <h2>{lastModifiedResult.title}</h2>
              <div className="result-details">
                <div>
                  <span>Affected slide{lastModifiedResult.affected_slides.length === 1 ? "" : "s"}</span>
                  <strong>{formatSlides(lastModifiedResult.affected_slides)}</strong>
                </div>
                <div>
                  <span>New version created</span>
                  <strong>{versionLabel(lastModifiedResult.file_name) ?? lastModifiedResult.file_name}</strong>
                </div>
                <div className="file-path"><span>Updated file</span><strong>{lastModifiedResult.file_name}</strong></div>
              </div>
              <p className="success-message">{selectiveSummary(lastModifiedResult)}</p>
              <a
                className="generate-button"
                href={fileDownloadUrl(lastModifiedResult.file_name)}
                download={lastModifiedResult.file_name}
              >
                Download Updated PowerPoint <span aria-hidden="true">↓</span>
              </a>
            </div>
          </section>
        )}

        {modifyResult && modifyResult.status !== "regenerated" && (
          <section className="result-card error-card" role="alert">
            <div className="result-icon error-icon" aria-hidden="true">!</div>
            <div>
              <h2>
                {modifyResult.status === "clarification_needed"
                  ? "We need a more specific request"
                  : "This change affects the whole presentation"}
              </h2>
              <p>{modifyResult.message}</p>
            </div>
          </section>
        )}
      </section>

      <footer className="page-footer">A project demo for structured, prompt-driven presentation generation.</footer>
    </main>
  );
}
