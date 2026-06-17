import { NextRequest, NextResponse } from 'next/server';

const API_KEY = process.env.SARVAM_API_KEY ?? '';
const BASE_URL = 'https://api.sarvam.ai/doc-digitization/job/v1';
const HEADERS = { 'api-subscription-key': API_KEY, 'Content-Type': 'application/json' };

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
      body: JSON.stringify({ output_format: 'md' }),
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
      headers: { 'Content-Type': 'application/pdf' },
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

    // Step 7: Download the markdown output
    const downloadUrls: Record<string, { file_url: string }> = downloadData.download_urls;
    const mdEntry = Object.entries(downloadUrls).find(([name]) => name.endsWith('.md'));
    if (!mdEntry) throw new Error('No markdown output file found in results');

    const mdRes = await fetch(mdEntry[1].file_url);
    if (!mdRes.ok) throw new Error(`Failed to download markdown: ${mdRes.status}`);
    const content = await mdRes.text();

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
