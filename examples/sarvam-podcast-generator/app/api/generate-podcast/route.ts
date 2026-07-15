import { NextRequest, NextResponse } from 'next/server';
import { v4 as uuidv4 } from 'uuid';
import { inngest } from '../../../lib/inngest';
import { createJob } from '../../../lib/job-store';

export const maxDuration = 60;
export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  try {
    const { content, language, title } = await request.json();

    if (!content) {
      return NextResponse.json({ error: 'Content is required' }, { status: 400 });
    }

    const targetLanguage = language || 'en-IN';
    const jobId = uuidv4();

    // Create job in store
    await createJob(jobId);

    // Send event to Inngest to start background processing
    await inngest.send({
      name: 'podcast/generate',
      data: {
        content,
        language: targetLanguage,
        title,
        jobId
      }
    });

    console.log(`Podcast generation job ${jobId} queued successfully`);

    return NextResponse.json({
      jobId,
      status: 'pending',
      message: 'Podcast generation started. Use the jobId to check status.',
      statusUrl: `/api/job-status/${jobId}`
    });

  } catch (error) {
    console.error('Error starting podcast generation:', error);

    let errorMessage = 'Failed to start podcast generation';
    if (error instanceof Error) {
      errorMessage = error.message;
    }

    return NextResponse.json(
      {
        error: `Error starting podcast generation: ${errorMessage}`
      },
      { status: 500 }
    );
  }
}
