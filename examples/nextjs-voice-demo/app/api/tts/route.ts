import { NextRequest, NextResponse } from "next/server";
import type { TTSRequest, SarvamTTSResponse } from "@/lib/types";
import { TTS_MODEL, MAX_TTS_CHARS } from "@/lib/constants";

export async function POST(request: NextRequest) {
  try {
    const body: TTSRequest = await request.json();
    const { text, language, speaker } = body;

    // ── Validate input ──────────────────────────────────────────────────────
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

    // ── API key ─────────────────────────────────────────────────────────────
    const apiKey = process.env.SARVAM_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: "SARVAM_API_KEY is not configured on the server" },
        { status: 500 }
      );
    }

    // ── Call Sarvam TTS ─────────────────────────────────────────────────────
    const sarvamRes = await fetch("https://api.sarvam.ai/text-to-speech", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "api-subscription-key": apiKey,
      },
      body: JSON.stringify({
        inputs: [text],
        target_language_code: language,
        speaker,
        pace: 1.0,
        temperature: 0.6,
        speech_sample_rate: 22050,
        model: TTS_MODEL,
      }),
    });

    if (!sarvamRes.ok) {
      const errorText = await sarvamRes.text();
      console.error("[TTS] Sarvam API error:", errorText);
      return NextResponse.json(
        { error: `Sarvam API error (${sarvamRes.status}): ${errorText}` },
        { status: sarvamRes.status }
      );
    }

    const data: SarvamTTSResponse = await sarvamRes.json();

    if (!data.audios || data.audios.length === 0) {
      return NextResponse.json(
        { error: "No audio returned from Sarvam API" },
        { status: 500 }
      );
    }

    return NextResponse.json({ audioBase64: data.audios[0] });
  } catch (error) {
    console.error("[TTS] Unexpected error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Internal server error" },
      { status: 500 }
    );
  }
}
