import { NextRequest, NextResponse } from "next/server";
import type { TTSRequest, SarvamTTSResponse } from "@/lib/types";
import { TTS_MODEL, MAX_TTS_CHARS } from "@/lib/constants";
import { getApiKey, jsonHeaders, handleSarvamError, handleUnexpectedError, SARVAM_API_BASE } from "@/lib/sarvam";

export async function POST(request: NextRequest) {
  try {
    const body: TTSRequest = await request.json();
    const { text, language, speaker } = body;

    // ── Validate ──────────────────────────────────────────────────────────────
    if (!text || !language || !speaker) {
      return NextResponse.json(
        { error: "Missing required fields: text, language, speaker" },
        { status: 400 }
      );
    }
    if (text.trim().length === 0) {
      return NextResponse.json({ error: "Text cannot be empty" }, { status: 400 });
    }
    if (text.length > MAX_TTS_CHARS) {
      return NextResponse.json(
        { error: `Text must be ${MAX_TTS_CHARS} characters or fewer` },
        { status: 400 }
      );
    }

    // ── API key ───────────────────────────────────────────────────────────────
    const { key, error: keyError } = getApiKey();
    if (keyError) return keyError;

    // ── Call Sarvam TTS ───────────────────────────────────────────────────────
    const sarvamRes = await fetch(`${SARVAM_API_BASE}/text-to-speech`, {
      method: "POST",
      headers: jsonHeaders(key),
      body: JSON.stringify({
        inputs:               [text],
        target_language_code: language,
        speaker,
        pace:                 1.0,
        temperature:          0.6,
        speech_sample_rate:   22050,
        model:                TTS_MODEL,
      }),
    });

    if (!sarvamRes.ok) return handleSarvamError(sarvamRes, "TTS");

    const data: SarvamTTSResponse = await sarvamRes.json();
    if (!data.audios?.length) {
      return NextResponse.json({ error: "No audio returned from Sarvam API" }, { status: 500 });
    }

    return NextResponse.json({ audioBase64: data.audios[0] });
  } catch (error) {
    return handleUnexpectedError(error, "TTS");
  }
}
