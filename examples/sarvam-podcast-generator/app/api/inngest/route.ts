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
  // Only pass a signing key in production; passing an empty string breaks the dev handshake.
  ...(process.env.INNGEST_SIGNING_KEY
    ? { signingKey: process.env.INNGEST_SIGNING_KEY }
    : {}),
}); 