import { NextRequest, NextResponse } from "next/server";
import type { TransliterateRequest, SarvamTransliterateResponse } from "@/lib/types";
import { getApiKey, jsonHeaders, handleSarvamError, handleUnexpectedError, SARVAM_API_BASE } from "@/lib/sarvam";

export async function POST(request: NextRequest) {
  try {
    const body: TransliterateRequest = await request.json();
    const { text, sourceLanguage, targetLanguage } = body;

    // ── Validate ──────────────────────────────────────────────────────────────
    if (!text || !targetLanguage) {
      return NextResponse.json(
        { error: "Missing required fields: text, targetLanguage" },
        { status: 400 }
      );
    }
    if (text.trim().length === 0) {
      return NextResponse.json({ error: "Text cannot be empty" }, { status: 400 });
    }

    // ── API key ───────────────────────────────────────────────────────────────
    const { key, error: keyError } = getApiKey();
    if (keyError) return keyError;

    // ── Call Sarvam Transliterate ─────────────────────────────────────────────
    const sarvamRes = await fetch(`${SARVAM_API_BASE}/transliterate`, {
      method:  "POST",
      headers: jsonHeaders(key),
      body: JSON.stringify({
        input:                text,
        source_language_code: sourceLanguage ?? "en-IN",
        target_language_code: targetLanguage,
      }),
    });

    if (!sarvamRes.ok) return handleSarvamError(sarvamRes, "Transliterate");

    const data: SarvamTransliterateResponse = await sarvamRes.json();
    return NextResponse.json({
      transliterated_text: data.transliterated_text ?? "",
    });
  } catch (error) {
    return handleUnexpectedError(error, "Transliterate");
  }
}
