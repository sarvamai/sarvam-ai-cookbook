import { NextRequest, NextResponse } from "next/server";
import type { SarvamSTTResponse } from "@/lib/types";
import { STT_MODEL } from "@/lib/constants";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;
    const languageCode = (formData.get("language_code") as string | null) ?? "hi-IN";

    // ── Validate input ──────────────────────────────────────────────────────
    if (!file) {
      return NextResponse.json({ error: "No audio file provided" }, { status: 400 });
    }

    if (file.size === 0) {
      return NextResponse.json({ error: "Audio file is empty" }, { status: 400 });
    }

    // ── API key ─────────────────────────────────────────────────────────────
    const apiKey = process.env.SARVAM_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: "SARVAM_API_KEY is not configured on the server" },
        { status: 500 }
      );
    }

    // ── Forward to Sarvam STT ───────────────────────────────────────────────
    // Note: Do NOT set Content-Type here — fetch must auto-set the
    // multipart/form-data boundary.
    const sarvamForm = new FormData();
    sarvamForm.append("file", file, file.name || "audio.wav");
    sarvamForm.append("language_code", languageCode);
    sarvamForm.append("model", STT_MODEL);
    sarvamForm.append("with_timestamps", "false");

    const sarvamRes = await fetch("https://api.sarvam.ai/speech-to-text", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "api-subscription-key": apiKey,
      },
      body: sarvamForm,
    });

    if (!sarvamRes.ok) {
      const errorText = await sarvamRes.text();
      console.error("[STT] Sarvam API error:", errorText);
      return NextResponse.json(
        { error: `Sarvam API error (${sarvamRes.status}): ${errorText}` },
        { status: sarvamRes.status }
      );
    }

    const data: SarvamSTTResponse = await sarvamRes.json();

    return NextResponse.json({
      transcript: data.transcript ?? "",
      language_code: data.language_code,
    });
  } catch (error) {
    console.error("[STT] Unexpected error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Internal server error" },
      { status: 500 }
    );
  }
}
