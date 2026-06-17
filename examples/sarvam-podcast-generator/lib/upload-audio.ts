// Local dev: stores audio as base64 data URLs in-memory — no UploadThing token needed.
interface AudioRecord {
  customId: string;
  fileKey: string;
  jobId: string;
}

const audioRecords: AudioRecord[] = [];

export async function uploadBase64AudioWithCleanup(
  audioBase64: string,
  fileName: string,
  customId: string,
  deleteAfterMinutes: number,
  jobId: string
): Promise<{ url: string; fileKey: string }> {
  const url = `data:audio/wav;base64,${audioBase64}`;
  const fileKey = `local-${customId}`;
  audioRecords.push({ customId, fileKey, jobId });
  return { url, fileKey };
}

export async function fetchAudioDataUrl(url: string): Promise<string> {
  if (url.startsWith('data:')) return url;
  const response = await fetch(url);
  const arrayBuffer = await response.arrayBuffer();
  const base64 = Buffer.from(arrayBuffer).toString('base64');
  const mimeType = response.headers.get('content-type') ?? 'audio/wav';
  return `data:${mimeType};base64,${base64}`;
}
