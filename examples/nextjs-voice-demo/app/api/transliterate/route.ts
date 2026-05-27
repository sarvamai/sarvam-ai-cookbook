import { NextRequest, NextResponse } from "next/server";
import type { TransliterateRequest, SarvamTransliterateResponse } from "@/lib/types";

export async function POST(request: NextRequest) {
  try {
    const body: TransliterateRequest = await request.json();
    const { text, sourceLanguage, targetLanguage } = body;

    // ── Validate input ──────────────────────────────────────────────────────
    if (!text || !targetLanguage) {
      return NextResponse.json(
        { error: "Missing required fields: text, targetLanguage" },
        { status: 400 }
      );
    }

    if (text.trim().length === 0) {
      return NextResponse.json({ error: "Text cannot be empty" }, { status: 400 });
    }

    // ── API key ─────────────────────────────────────────────────────────────
    const apiKey = process.env.SARVAM_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: "SARVAM_API_KEY is not configured on the server" },
        { status: 500 }
      );
    }

    // ── Call Sarvam Transliterate ───────────────────────────────────────────
    const sarvamRes = await fetch("https://api.sarvam.ai/transliterate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "api-subscription-key": apiKey,
      },
      body: JSON.stringify({
        input: text,
        source_language_code: sourceLanguage ?? "en-IN",
        target_language_code: targetLanguage,
      }),
    });

    if (!sarvamRes.ok) {
      const errorText = await sarvamRes.text();
      console.error("[Transliterate] Sarvam API error:", errorText);
      return NextResponse.json(
        { error: `Sarvam API error (${sarvamRes.status}): ${errorText}` },
        { status: sarvamRes.status }
      );
    }

    const data: SarvamTransliterateResponse = await sarvamRes.json();

    return NextResponse.json({
      transliterated_text: data.transliterated_text ?? "",
    });
  } catch (error) {
    console.error("[Transliterate] Unexpected error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Internal server error" },
      { status: 500 }
    );
  }
}
