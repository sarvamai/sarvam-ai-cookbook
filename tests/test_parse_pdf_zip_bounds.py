"""Regression tests for ZIP bounds and decompression safety in parse-pdf route."""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROUTE_PATH = Path("examples/sarvam-podcast-generator/app/api/parse-pdf/route.ts")


def _run_extract_in_node(tmp_path: Path, zip_bytes: bytes, extensions: list[str]) -> dict:
    """Execute extractTextFromZip from route.ts inside Node.js without Next.js runtime."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node executable not available")

    source = ROUTE_PATH.read_text(encoding="utf-8")
    # Extract ZipValidationError and extractTextFromZip up to `async function pollStatus`
    start = source.index("const MAX_ZIP_ENTRIES")
    end = source.index("async function pollStatus")
    ts_snippet = source[start:end]

    script = (
        "import { inflateRawSync } from 'zlib';\n"
        + ts_snippet
        + "\nconst buf = Buffer.from(process.argv[2], 'base64');\n"
        + "const exts = JSON.parse(process.argv[3]);\n"
        + "try {\n"
        + "  const out = extractTextFromZip(buf, exts);\n"
        + "  console.log(JSON.stringify({ ok: true, out }));\n"
        + "} catch (err: unknown) {\n"
        + "  const e = err as Error;\n"
        + "  console.log(JSON.stringify({ ok: false, name: e.name, message: e.message }));\n"
        + "}\n"
    )
    import base64

    script_file = tmp_path / "run_extract.mts"
    script_file.write_text(script, encoding="utf-8")

    proc = subprocess.run(
        [
            node,
            "--experimental-strip-types",
            str(script_file),
            base64.b64encode(zip_bytes).decode("ascii"),
            json.dumps(extensions),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_parse_pdf_valid_zip_stored_and_deflated(tmp_path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("doc.md", "# Title\nHello", compress_type=zipfile.ZIP_STORED)
        zf.writestr("notes.txt", "World", compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("ignored.png", b"\x89PNG", compress_type=zipfile.ZIP_STORED)

    res = _run_extract_in_node(tmp_path, buf.getvalue(), [".md", ".txt", ".html"])
    assert res["ok"] is True
    assert "# Title\nHello" in res["out"]
    assert "World" in res["out"]


def test_parse_pdf_rejects_out_of_bounds_zip_without_range_error(tmp_path: Path):
    # Craft an EOCD claiming 1 entry with out-of-bounds central directory offset.
    bad = bytearray(22)
    bad[0:4] = b"PK\x05\x06"
    bad[10:12] = (1).to_bytes(2, "little")
    bad[16:20] = (9999).to_bytes(4, "little")

    res = _run_extract_in_node(tmp_path, bytes(bad), [".md"])
    assert res["ok"] is False
    assert res["name"] == "ZipValidationError"


def test_parse_pdf_blocks_decompression_bomb(tmp_path: Path):
    # 11 MB of zeros compresses to ~11 KB via deflate, exceeding 10 MB per-entry cap.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bomb.txt", b"\x00" * (11 * 1024 * 1024))

    res = _run_extract_in_node(tmp_path, buf.getvalue(), [".txt"])
    assert res["ok"] is False
    assert res["name"] == "ZipValidationError"
    assert "size limit" in res["message"].lower() or "exceeds" in res["message"].lower()


def test_parse_pdf_route_enforces_max_output_length():
    text = ROUTE_PATH.read_text(encoding="utf-8")
    assert re.search(r"maxOutputLength\s*:", text)
    assert "ZipValidationError" in text
