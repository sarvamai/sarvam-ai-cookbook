import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createJob, getJobStatus, updateJobStatus } from './job-store';

const globalForJobs = globalThis as typeof globalThis & {
  __jobStore?: Map<string, unknown>;
  __jobRedis?: unknown;
};

describe('job store', () => {
  beforeEach(() => {
    delete process.env.UPSTASH_REDIS_REST_URL;
    delete process.env.UPSTASH_REDIS_REST_TOKEN;
    globalForJobs.__jobStore?.clear();
    delete globalForJobs.__jobRedis;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    delete process.env.UPSTASH_REDIS_REST_URL;
    delete process.env.UPSTASH_REDIS_REST_TOKEN;
  });

  it('uses the in-memory store when Upstash is not configured', async () => {
    await createJob('local-job');
    await updateJobStatus('local-job', 'processing');

    const job = await getJobStatus('local-job');

    expect(job?.status).toBe('processing');
    expect(job?.createdAt).toBeInstanceOf(Date);
    expect(job?.updatedAt).toBeInstanceOf(Date);
  });

  it('stores jobs in Upstash and restores dates when reading them', async () => {
    const stored = new Map<string, string>();
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const [[command, key, value]] = JSON.parse(String(init?.body)) as string[][];

      if (command === 'set' && key && value) {
        stored.set(key, value);
        return Response.json([{ result: 'OK' }]);
      }

      return Response.json([{ result: key ? stored.get(key) ?? null : null }]);
    });
    vi.stubGlobal('fetch', fetchMock);
    process.env.UPSTASH_REDIS_REST_URL = 'https://redis.example';
    process.env.UPSTASH_REDIS_REST_TOKEN = 'test-token';

    await createJob('shared-job');
    await updateJobStatus('shared-job', 'completed', { audioUrl: 'https://audio.example' });
    globalForJobs.__jobStore?.clear();

    const job = await getJobStatus('shared-job');

    expect(job).toMatchObject({
      id: 'shared-job',
      status: 'completed',
      result: { audioUrl: 'https://audio.example' },
    });
    expect(job?.createdAt).toBeInstanceOf(Date);
    expect(job?.updatedAt).toBeInstanceOf(Date);
    expect(fetchMock).toHaveBeenCalled();
  });

  it('rejects incomplete Upstash configuration', async () => {
    process.env.UPSTASH_REDIS_REST_URL = 'https://redis.example';

    await expect(createJob('misconfigured-job')).rejects.toThrow(
      'Both UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN must be configured'
    );
  });

  it('does not silently use the in-memory store in production', async () => {
    vi.stubEnv('NODE_ENV', 'production');

    await expect(createJob('production-job')).rejects.toThrow(
      'Upstash Redis must be configured in production'
    );
  });
});
