export interface Job {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result?: any;
  error?: string;
  createdAt: Date;
  updatedAt: Date;
}

// Pin the store to globalThis so it's a single process-wide singleton.
// Without this, each Next.js route bundle (generate-podcast, job-status, inngest)
// gets its own module copy and the Map isn't shared — causing "job not found".
const globalForJobs = globalThis as unknown as { __jobStore?: Map<string, Job> };
const jobs = globalForJobs.__jobStore ?? new Map<string, Job>();
globalForJobs.__jobStore = jobs;

export async function createJob(id: string): Promise<Job> {
  const job: Job = {
    id,
    status: 'pending',
    createdAt: new Date(),
    updatedAt: new Date(),
  };
  jobs.set(id, job);
  return job;
}

export async function updateJobStatus(
  id: string,
  status: Job['status'],
  result?: any,
  error?: string
): Promise<void> {
  const job = jobs.get(id);
  if (!job) throw new Error(`Job ${id} not found`);
  job.status = status;
  job.updatedAt = new Date();
  if (result !== undefined) job.result = result;
  if (error !== undefined) job.error = error;
}

export async function getJobStatus(id: string): Promise<Job | null> {
  return jobs.get(id) ?? null;
}
