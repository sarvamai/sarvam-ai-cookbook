#!/usr/bin/env python3
"""
Anthropic-to-Sarvam proxy.

Claude Code CLI speaks the Anthropic Messages API.
Sarvam AI speaks the OpenAI Chat Completions API.
This proxy sits in between: it accepts Anthropic-format requests on
http://localhost:8082/v1/messages, translates them to OpenAI format,
forwards to Sarvam AI, and translates the response back.

Supports both streaming and non-streaming responses, plus basic tool-use
pass-through (needed for Claude Code's file/bash tools).

Usage:
    export SARVAM_API_KEY=your_key
    python proxy.py
"""

import json
import os
import uuid
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

app = FastAPI(title="Anthropic-to-Sarvam Proxy")

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
SARVAM_BASE_URL = "https://api.sarvam.ai/v1"
SARVAM_MODEL = "sarvam-m"
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8082"))

# Claude Code defaults max_tokens to ~64000 (a Claude-sized value), which
# Sarvam rejects. Two limits apply:
#   - The model itself has a 7192-token total context window.
#   - The Sarvam starter (free) tier caps max_tokens at 2048 per request.
# Default to the starter-tier ceiling so this works out of the box; users on
# higher tiers can raise it via the MAX_OUTPUT_TOKENS env var.
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "2048"))


# ---------------------------------------------------------------------------
# Format translation helpers
# ---------------------------------------------------------------------------


def _content_to_str(content) -> str:
    """Flatten Anthropic content (string or content-block list) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return ""


def anthropic_to_openai_messages(body: dict) -> list[dict]:
    """Convert an Anthropic request body to an OpenAI messages list.

    sarvam-m does not support OpenAI function calling, so we flatten any
    tool_use / tool_result blocks into plain text rather than emitting
    OpenAI-style tool_calls / tool messages. This keeps the conversation
    coherent even when Claude Code's history contains tool turns.
    """
    messages: list[dict] = []

    # Top-level system prompt
    system = body.get("system")
    if system:
        messages.append({"role": "system", "content": _content_to_str(system)})

    for msg in body.get("messages", []):
        role = msg["role"]
        content = msg["content"]

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue

        # Flatten content blocks into a single text string
        parts: list[str] = []
        for block in content:
            btype = block.get("type", "")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_use":
                name = block.get("name", "")
                args = json.dumps(block.get("input", {}), ensure_ascii=False)
                parts.append(f"[tool_use: {name} {args}]")
            elif btype == "tool_result":
                rc = block.get("content", "")
                if isinstance(rc, list):
                    rc = " ".join(
                        b.get("text", "") for b in rc if b.get("type") == "text"
                    )
                parts.append(f"[tool_result: {rc}]")

        flat = "\n".join(p for p in parts if p)
        if flat:
            messages.append({"role": role, "content": flat})

    return messages


def openai_to_anthropic_response(oai: dict) -> dict:
    """Convert an OpenAI chat completion response to Anthropic Messages format."""
    choice = oai["choices"][0]
    message = choice.get("message", {})

    content = [{"type": "text", "text": message.get("content", "") or ""}]

    _stop_map = {"stop": "end_turn", "length": "max_tokens"}
    stop_reason = _stop_map.get(choice.get("finish_reason", "stop"), "end_turn")
    usage = oai.get("usage", {})

    return {
        "id": oai.get("id", f"msg_{uuid.uuid4().hex}"),
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": SARVAM_MODEL,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


# ---------------------------------------------------------------------------
# Streaming translation
# ---------------------------------------------------------------------------


async def _stream_openai_to_anthropic(oai_resp: httpx.Response, message_id: str):
    """Yield Anthropic SSE events translated from an OpenAI SSE stream."""

    # ── message_start ──────────────────────────────────────────────────────
    yield (
        "event: message_start\n"
        f"data: {json.dumps({'type': 'message_start', 'message': {'id': message_id, 'type': 'message', 'role': 'assistant', 'content': [], 'model': SARVAM_MODEL, 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n\n"
    )
    yield f"event: ping\ndata: {json.dumps({'type': 'ping'})}\n\n"

    yield (
        "event: content_block_start\n"
        f"data: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
    )

    output_tokens = 0

    async for line in oai_resp.aiter_lines():
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break

        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue

        choices = chunk.get("choices") or []
        if not choices:
            continue
        text = (choices[0].get("delta") or {}).get("content") or ""
        if not text:
            continue

        output_tokens += 1
        yield (
            "event: content_block_delta\n"
            f"data: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': text}})}\n\n"
        )

    yield (
        "event: content_block_stop\n"
        f"data: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
    )

    # ── message_delta + message_stop ────────────────────────────────────
    yield (
        "event: message_delta\n"
        f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': output_tokens}})}\n\n"
    )
    yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@app.post("/v1/messages")
async def messages(request: Request):
    if not SARVAM_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="SARVAM_API_KEY environment variable is not set.",
        )

    body = await request.json()
    stream = body.get("stream", False)

    openai_messages = anthropic_to_openai_messages(body)

    # One-line trace so you can confirm requests are landing on the proxy
    # (and therefore going to Sarvam, not Anthropic).
    last_user = next(
        (m["content"] for m in reversed(openai_messages) if m["role"] == "user"),
        "",
    )
    preview = (last_user[:80] + "…") if len(last_user) > 80 else last_user
    print(
        f"→ sarvam-m  stream={stream}  msgs={len(openai_messages)}  "
        f"max_tokens={min(body.get('max_tokens', MAX_OUTPUT_TOKENS), MAX_OUTPUT_TOKENS)}  "
        f"user={preview!r}",
        flush=True,
    )

    openai_payload: dict = {
        "model": SARVAM_MODEL,
        "messages": openai_messages,
        "max_tokens": min(body.get("max_tokens", MAX_OUTPUT_TOKENS), MAX_OUTPUT_TOKENS),
        "stream": stream,
    }

    if body.get("temperature") is not None:
        openai_payload["temperature"] = body["temperature"]

    if body.get("top_p") is not None:
        openai_payload["top_p"] = body["top_p"]

    # NOTE: sarvam-m does not support function calling. Tool definitions from
    # Claude Code are deliberately not forwarded; the model replies in text only.

    headers = {
        "Authorization": f"Bearer {SARVAM_API_KEY}",
        "Content-Type": "application/json",
    }

    if stream:
        message_id = f"msg_{uuid.uuid4().hex}"

        async def generate():
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{SARVAM_BASE_URL}/chat/completions",
                    headers=headers,
                    json=openai_payload,
                    timeout=120,
                ) as resp:
                    if resp.status_code != 200:
                        body_text = await resp.aread()
                        yield (
                            "event: error\n"
                            f"data: {json.dumps({'type': 'error', 'error': {'type': 'api_error', 'message': body_text.decode()}})}\n\n"
                        )
                        return
                    async for chunk in _stream_openai_to_anthropic(resp, message_id):
                        yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SARVAM_BASE_URL}/chat/completions",
            headers=headers,
            json=openai_payload,
            timeout=120,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    return JSONResponse(openai_to_anthropic_response(resp.json()))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if not SARVAM_API_KEY:
        print("Error: SARVAM_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    print(f"Starting Anthropic-to-Sarvam proxy on http://localhost:{PROXY_PORT}")
    print(f"Routing all requests to {SARVAM_MODEL} via {SARVAM_BASE_URL}")
    uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT, log_level="warning")
