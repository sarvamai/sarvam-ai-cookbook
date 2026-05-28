/**
 * Format seconds as MM:SS — used by the STT recording timer.
 */
export function fmtTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/**
 * Convert a base64-encoded WAV string into an object URL that can be
 * used directly as an <audio> src or passed to new Audio().
 */
export function base64ToAudioUrl(base64: string): string {
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const blob  = new Blob([bytes], { type: "audio/wav" });
  return URL.createObjectURL(blob);
}

/**
 * Strip codec parameters from a MIME type.
 * Sarvam's STT API rejects "audio/webm;codecs=opus" — normalise to "audio/webm".
 */
export function normaliseMimeType(mimeType: string): string {
  return mimeType.split(";")[0].trim();
}
