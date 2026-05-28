/**
 * Shared server-side helpers for calling the Sarvam AI API.
 * Imported only by Next.js Route Handlers — never bundled client-side.
 */
import { NextResponse } from "next/server";

export const SARVAM_API_BASE = "https://api.sarvam.ai";

// ── API key ───────────────────────────────────────────────────────────────────

type ApiKeyResult =
  | { key: string;    error: null }
  | { key: null;      error: NextResponse };

/**
 * Read the Sarvam API key from the environment.
 * Returns an error NextResponse if the key is missing so callers can return early.
 */
export function getApiKey(): ApiKeyResult {
  const key = process.env.SARVAM_API_KEY;
  if (!key) {
    return {
      key:   null,
      error: NextResponse.json(
        { error: "SARVAM_API_KEY is not configured on the server." },
        { status: 500 }
      ),
    };
  }
  return { key, error: null };
}

// ── Request headers ───────────────────────────────────────────────────────────

/** Headers for JSON POST requests to Sarvam */
export function jsonHeaders(apiKey: string): Record<string, string> {
  return {
    "Content-Type":        "application/json",
    "api-subscription-key": apiKey,
  };
}

/**
 * Headers for multipart/form-data POST requests to Sarvam.
 * Note: do NOT set Content-Type here — the Fetch API must set it automatically
 * so the multipart boundary is included correctly.
 */
export function multipartHeaders(apiKey: string): Record<string, string> {
  return {
    "api-subscription-key": apiKey,
  };
}

// ── Error handling ────────────────────────────────────────────────────────────

/** Parse and forward a non-OK response from the Sarvam API */
export async function handleSarvamError(
  res: Response,
  context: string
): Promise<NextResponse> {
  let message = `Sarvam ${context} API error (${res.status})`;
  try {
    const body = await res.json();
    if (body?.message) message = body.message;
    else if (body?.error) message = body.error;
  } catch { /* ignore parse errors */ }
  return NextResponse.json({ error: message }, { status: res.status });
}

/** Catch-all for unexpected thrown errors */
export function handleUnexpectedError(
  error: unknown,
  context: string
): NextResponse {
  const message =
    error instanceof Error ? error.message : `Unexpected ${context} error`;
  return NextResponse.json({ error: message }, { status: 500 });
}
