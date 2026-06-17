import { NextRequest, NextResponse } from 'next/server';
import { inflateRawSync } from 'zlib';

const API_KEY = process.env.SARVAM_API_KEY ?? '';
const BASE_URL = 'https://api.sarvam.ai/doc-digitization/job/v1';
const HEADERS = { 'api-subscription-key': API_KEY, 'Content-Type': 'application/json' };

// Minimal ZIP extractor using the central directory — no external dependency.
// Returns concatenated text of all entries whose name ends with one of `extensions`.
function extractTextFromZip(buf: Buffer, extensions: string[]): string {
  // Locate End of Central Directory record (signature 0x06054b50), searching from the end.
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd === -1) throw new Error('Invalid ZIP: no end-of-central-directory record');

  const total = buf.readUInt16LE(eocd + 10);
  let ptr = buf.readUInt32LE(eocd + 16); // offset of start of central directory

  const parts: string[] = [];
  for (let n = 0; n < total; n++) {
    if (buf.readUInt32LE(ptr) !== 0x02014b50) break; // central dir file header signature
    const method = buf.readUInt16LE(ptr + 10);
    const compSize = buf.readUInt32LE(ptr + 20);
    const fnLen = buf.readUInt16LE(ptr + 28);
    const extraLen = buf.readUInt16LE(ptr + 30);
    const commentLen = buf.readUInt16LE(ptr + 32);
    const localOffset = buf.readUInt32LE(ptr + 42);
    const name = buf.toString('utf8', ptr + 46, ptr + 46 + fnLen);

    if (extensions.some(ext => name.toLowerCase().endsWith(ext))) {
      // Read the local header to find where the actual data starts.
      const lfnLen = buf.readUInt16LE(localOffset + 26);
      const lextraLen = buf.readUInt16LE(localOffset + 28);
      const dataStart = localOffset + 30 + lfnLen + lextraLen;
      const compData = buf.subarray(dataStart, dataStart + compSize);
      const raw = method === 0 ? compData : inflateRawSync(compData); // 0 = stored, 8 = deflate
      parts.push(raw.toString('utf8'));
    }

    ptr += 46 + fnLen + extraLen + commentLen;
  }

  return parts.join('\n\n');
}

async function pollStatus(jobId: string, maxWaitMs = 120000): Promise<string> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const res = await fetch(`${BASE_URL}/${jobId}/status`, {
      headers: { 'api-subscription-key': API_KEY },
    });
    if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
    const data = await res.json();
    const state: string = data.job_state;
    if (state === 'Completed' || state === 'PartiallyCompleted') return state;
    if (state === 'Failed') throw new Error('Document Intelligence job failed');
    await new Promise(resolve => setTimeout(resolve, 3000));
  }
  throw new Error('Document Intelligence job timed out');
}

export async function POST(request: NextRequest) {
  try {
    if (!API_KEY) {
      return NextResponse.json({ error: 'SARVAM_API_KEY not configured' }, { status: 500 });
    }

    const formData = await request.formData();
    const file = formData.get('pdf') as File;

    if (!file) return NextResponse.json({ error: 'No PDF file provided' }, { status: 400 });
    if (file.type !== 'application/pdf') return NextResponse.json({ error: 'Only PDF files are allowed' }, { status: 400 });

    // Step 1: Create job
    const createRes = await fetch(BASE_URL, {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify({ job_parameters: { output_format: 'md', language: 'en-IN' } }),
    });
    if (!createRes.ok) throw new Error(`Failed to create job: ${await createRes.text()}`);
    const { job_id } = await createRes.json();

    // Step 2: Get presigned upload URL
    const uploadUrlRes = await fetch(`${BASE_URL}/upload-files`, {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify({ job_id, files: [file.name] }),
    });
    if (!uploadUrlRes.ok) throw new Error(`Failed to get upload URL: ${await uploadUrlRes.text()}`);
    const uploadData = await uploadUrlRes.json();
    const presignedUrl: string = uploadData.upload_urls[file.name]?.file_url;
    if (!presignedUrl) throw new Error('No presigned upload URL returned');

    // Step 3: Upload PDF to presigned URL
    const arrayBuffer = await file.arrayBuffer();
    const uploadRes = await fetch(presignedUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/pdf',
        'x-ms-blob-type': 'BlockBlob', // Required for Azure Blob Storage presigned uploads
      },
      body: arrayBuffer,
    });
    if (!uploadRes.ok) throw new Error(`Failed to upload PDF: ${uploadRes.status}`);

    // Step 4: Start job
    const startRes = await fetch(`${BASE_URL}/${job_id}/start`, {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify({}),
    });
    if (!startRes.ok) throw new Error(`Failed to start job: ${await startRes.text()}`);

    // Step 5: Poll until complete
    await pollStatus(job_id);

    // Step 6: Get download URLs
    const downloadUrlRes = await fetch(`${BASE_URL}/${job_id}/download-files`, {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify({}),
    });
    if (!downloadUrlRes.ok) throw new Error(`Failed to get download URLs: ${await downloadUrlRes.text()}`);
    const downloadData = await downloadUrlRes.json();

    // Step 7: Download the output. Results are delivered as a ZIP; the SDK grabs the
    // first download URL regardless of extension, so we do the same and unzip if needed.
    const downloadUrls: Record<string, { file_url: string }> = downloadData.download_urls;
    const firstEntry = Object.entries(downloadUrls)[0];
    if (!firstEntry) throw new Error('No output files found in results');

    const fileRes = await fetch(firstEntry[1].file_url);
    if (!fileRes.ok) throw new Error(`Failed to download output: ${fileRes.status}`);
    const fileBuf = Buffer.from(await fileRes.arrayBuffer());

    // Detect ZIP by magic bytes ("PK"); otherwise treat the body as plain markdown text.
    let content: string;
    if (fileBuf.length >= 2 && fileBuf[0] === 0x50 && fileBuf[1] === 0x4b) {
      content = extractTextFromZip(fileBuf, ['.md', '.txt', '.html']);
      if (!content.trim()) throw new Error('No text content found in ZIP output');
    } else {
      content = fileBuf.toString('utf8');
    }

    return NextResponse.json({
      content: content.trim(),
      images: [],
      metadata: {
        model: 'sarvam-vision',
        pagesProcessed: downloadData.job_details?.[0]?.pages_succeeded ?? 1,
      },
    });

  } catch (error) {
    console.error('Document Intelligence error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to process PDF' },
      { status: 500 }
    );
  }
}
