import { serve } from 'inngest/next';
import { inngest } from '../../../lib/inngest';
import { generatePodcastFunction } from '../../../inngest/podcast-generation';
import { audioCleanupFunction } from '../../../inngest/audio-cleanup';

export const { GET, POST, PUT } = serve({
  client: inngest,
  functions: [
    generatePodcastFunction,
    audioCleanupFunction
  ],
  signingKey: process.env.INNGEST_SIGNING_KEY,
}); 