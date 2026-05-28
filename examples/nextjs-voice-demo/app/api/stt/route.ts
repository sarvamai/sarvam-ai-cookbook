import { NextRequest, NextResponse } from "next/server";
import type { SarvamSTTResponse } from "@/lib/types";
import { STT_MODEL } from "@/lib/constants";
import { getApiKey, multipartHeaders, handleSarvamError, handleUnexpectedError, SARVAM_API_BASE } from "@/lib/sarvam";
import { normaliseMimeType } from "@/lib/utils";

export async function POST(request: NextRequest) {
  try {
    const formData     = await request.formData();
    const file         = formData.get("file") as File | null;
    const languageCode = (formData.get("language_code") as string | null) ?? "hi-IN";

    // ── Validate ──────────────────────────────────────────────────────────────
    if (!file)          return NextResponse.json({ error: "No audio file provided" }, { status: 400 });
    if (file.size === 0) return NextResponse.json({ error: "Audio file is empty" },   { status: 400 });

    // ── API key ───────────────────────────────────────────────────────────────
    const { key, error: keyError } = getApiKey();
    if (keyError) return keyError;

    // ── Normalise MIME type ───────────────────────────────────────────────────
    // Sarvam API rejects codec parameters e.g. "audio/webm;codecs=opus" → "audio/webm"
    const normalisedFile = new File(
      [file],
      file.name || "audio.wav",
      { type: normaliseMimeType(file.type) }
    );

    // ── Call Sarvam STT ───────────────────────────────────────────────────────
    const sarvamForm = new FormData();
    sarvamForm.append("file",            normalisedFile, normalisedFile.name);
    sarvamForm.append("language_code",   languageCode);
    sarvamForm.append("model",           STT_MODEL);
    sarvamForm.append("with_timestamps", "false");

    const sarvamRes = await fetch(`${SARVAM_API_BASE}/speech-to-text`, {
      method:  "POST",
      headers: multipartHeaders(key),
      body:    sarvamForm,
    });

    if (!sarvamRes.ok) return handleSarvamError(sarvamRes, "STT");

    const data: SarvamSTTResponse = await sarvamRes.json();
    return NextResponse.json({
      transcript:    data.transcript    ?? "",
      language_code: data.language_code,
    });
  } catch (error) {
    return handleUnexpectedError(error, "STT");
  }
}
