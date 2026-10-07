"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import {
  fileDownloadUrl,
  generatePresentation,
  GenerationResponse,
} from "../lib/api";

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<GenerationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!prompt.trim() || isGenerating) return;

    setIsGenerating(true);
    setError(null);
    setResult(null);
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

  return (
    <main className="app-shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="AI PowerPoint Generator home">
          <span className="brand-mark" aria-hidden="true">P</span>
          <span>Presentation Studio</span>
        </Link>
        <span className="status-chip"><span /> MVP preview</span>
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
            disabled={isGenerating}
            required
          />
          <div className="form-footer">
            <span className="input-hint">A few details about your audience and goals help shape the deck.</span>
            <span className="character-count">{prompt.length.toLocaleString()} / 20,000</span>
          </div>
          <button className="generate-button" type="submit" disabled={isGenerating || !prompt.trim()}>
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
      </section>

      <footer className="page-footer">A project demo for structured, prompt-driven presentation generation.</footer>
    </main>
  );
}
