export interface JobStatus {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result?: any;
  error?: string;
  createdAt: string;
  updatedAt: string;
}

export async function pollJobStatus(
  jobId: string,
  onStatusUpdate?: (status: JobStatus) => void,
  maxAttempts: number = 300,
  intervalMs: number = 3000
): Promise<JobStatus> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetch(`/api/job-status/${jobId}`);
    if (!response.ok) throw new Error(`Failed to check job status: ${response.statusText}`);

    const status: JobStatus = await response.json();
    onStatusUpdate?.(status);

    if (status.status === 'completed' || status.status === 'failed') {
      return status;
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  throw new Error('Job polling timed out after maximum attempts');
}
