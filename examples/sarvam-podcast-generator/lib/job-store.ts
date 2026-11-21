import { Redis } from '@upstash/redis';

export interface Job {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result?: any;
  error?: string;
  createdAt: Date;
  updatedAt: Date;
}

type StoredJob = Omit<Job, 'createdAt' | 'updatedAt'> & {
  createdAt: string;
  updatedAt: string;
};

const JOB_KEY_PREFIX = 'podcast-job:';
const globalForJobs = globalThis as typeof globalThis & {
  __jobStore?: Map<string, Job>;
  __jobRedis?: Redis;
};
const jobs = globalForJobs.__jobStore ?? new Map<string, Job>();
globalForJobs.__jobStore = jobs;

function getRedisClient(): Redis | null {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;

  if (!url && !token) {
    if (process.env.NODE_ENV === 'production') {
      throw new Error('Upstash Redis must be configured in production');
    }
    return null;
  }
  if (!url || !token) {
    throw new Error('Both UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN must be configured');
  }

  globalForJobs.__jobRedis ??= new Redis({ url, token });
  return globalForJobs.__jobRedis;
}

function serializeJob(job: Job): StoredJob {
  return {
    ...job,
    createdAt: job.createdAt.toISOString(),
    updatedAt: job.updatedAt.toISOString(),
  };
}

function deserializeJob(job: StoredJob): Job {
  return {
    ...job,
    createdAt: new Date(job.createdAt),
    updatedAt: new Date(job.updatedAt),
  };
}

export async function createJob(id: string): Promise<Job> {
  const job: Job = {
    id,
    status: 'pending',
    createdAt: new Date(),
    updatedAt: new Date(),
  };

  const redis = getRedisClient();
  if (redis) {
    await redis.set(`${JOB_KEY_PREFIX}${id}`, serializeJob(job));
  } else {
    jobs.set(id, job);
  }

  return job;
}

export async function updateJobStatus(
  id: string,
  status: Job['status'],
  result?: any,
  error?: string
): Promise<void> {
  const redis = getRedisClient();
  const key = `${JOB_KEY_PREFIX}${id}`;
  let job: Job | null;
  if (redis) {
    const storedJob = await redis.get<StoredJob>(key);
    job = storedJob ? deserializeJob(storedJob) : null;
  } else {
    job = jobs.get(id) ?? null;
  }

  if (!job) throw new Error(`Job ${id} not found`);
  job.status = status;
  job.updatedAt = new Date();
  if (result !== undefined) job.result = result;
  if (error !== undefined) job.error = error;

  if (redis) {
    await redis.set(key, serializeJob(job));
  } else {
    jobs.set(id, job);
  }
}

export async function getJobStatus(id: string): Promise<Job | null> {
  const redis = getRedisClient();
  if (!redis) return jobs.get(id) ?? null;

  const job = await redis.get<StoredJob>(`${JOB_KEY_PREFIX}${id}`);
  return job ? deserializeJob(job) : null;
}
