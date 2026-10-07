export interface GeneratePresentationRequest {
  prompt: string;
}

export interface GenerationResponse {
  success: boolean;
  run_id: string;
  presentation_id: string;
  title: string;
  slide_count: number;
  file_name: string;
  file_path: string;
}

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

function isGenerationResponse(value: unknown): value is GenerationResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Partial<GenerationResponse>;
  return (
    response.success === true &&
    typeof response.run_id === "string" &&
    typeof response.presentation_id === "string" &&
    typeof response.title === "string" &&
    response.title.trim().length > 0 &&
    typeof response.slide_count === "number" &&
    Number.isInteger(response.slide_count) &&
    response.slide_count > 0 &&
    typeof response.file_name === "string" &&
    response.file_name.trim().length > 0 &&
    typeof response.file_path === "string" &&
    response.file_path.trim().length > 0
  );
}

function getHttpErrorMessage(status: number): string {
  if (status === 422) {
    return "Please check your prompt. It must contain between 1 and 20,000 characters.";
  }
  if (status === 502) {
    return "The AI service could not complete this request. Please try again shortly.";
  }
  if (status === 503) {
    return "Presentation generation is not configured on the server yet.";
  }
  if (status === 500) {
    return "The server could not finish creating the PowerPoint file. Please try again.";
  }
  return "Presentation generation failed. Please try again.";
}

export function fileDownloadUrl(fileName: string): string {
  return `${API_BASE_URL}/api/files/${encodeURIComponent(fileName)}`;
}

export async function generatePresentation(
  prompt: string,
): Promise<GenerationResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt } satisfies GeneratePresentationRequest),
    });
  } catch {
    throw new Error(
      "Could not reach the presentation service. Check that the backend is running, then try again.",
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error("The server returned an unreadable response. Please try again.");
  }

  if (!response.ok) {
    // Do not surface raw FastAPI/LLM exception details in the user interface.
    throw new Error(getHttpErrorMessage(response.status));
  }

  if (!isGenerationResponse(payload)) {
    throw new Error("The server response was missing presentation details. Please try again.");
  }

  return payload;
}
