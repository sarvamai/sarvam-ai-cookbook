import { NextRequest, NextResponse } from 'next/server';
import { v4 as uuidv4 } from 'uuid';
import { inngest } from '../../../lib/inngest';
import { createJob } from '../../../lib/job-store';

export const maxDuration = 60;
export const dynamic = 'force-dynamic';

interface ScriptSegment {
  speaker: 'host' | 'guest';
  text: string;
}

interface AudioSegment {
  speaker: 'host' | 'guest';
  text: string;
  audioUrl: string;
}

const LANGUAGE_PROMPT_NAMES: { [key: string]: string } = {
  'hi-IN': 'Hindi',
  'en-IN': 'English',
  'ta-IN': 'Tamil',
  'te-IN': 'Telugu',
  'bn-IN': 'Bengali',
  'gu-IN': 'Gujarati',
  'mr-IN': 'Marathi',
  'ml-IN': 'Malayalam',
  'kn-IN': 'Kannada',
  'pa-IN': 'Punjabi',
  'od-IN': 'Odia'
};

// Voice mappings for different speakers
const VOICE_MAPPINGS: { [key: string]: { host: string; guest: string } } = {
  'hi-IN': { host: 'anushka', guest: 'karun' },
  'en-IN': { host: 'anushka', guest: 'karun' },
  'ta-IN': { host: 'anushka', guest: 'karun' },
  'te-IN': { host: 'anushka', guest: 'karun' },
  'bn-IN': { host: 'anushka', guest: 'karun' },
  'gu-IN': { host: 'anushka', guest: 'karun' },
  'mr-IN': { host: 'anushka', guest: 'karun' },
  'ml-IN': { host: 'anushka', guest: 'karun' },
  'kn-IN': { host: 'anushka', guest: 'karun' },
  'pa-IN': { host: 'anushka', guest: 'karun' },
  'od-IN': { host: 'anushka', guest: 'karun' }
};

async function callSarvamChat(messages: Array<{role: string, content: string}>, temperature: number = 0.7, maxTokens?: number, retryCount: number = 0): Promise<string> {
  const apiKey = process.env.SARVAM_API_KEY;
  if (!apiKey) {
    throw new Error('Sarvam API key not configured');
  }

  const requestBody: any = {
    messages,
    model: 'sarvam-m',
    temperature
  };

  if (maxTokens) {
    requestBody.max_tokens = maxTokens;
  }

  try {
    const response = await fetch('https://api.sarvam.ai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (response.status === 429) {
      const maxRetries = 3;
      if (retryCount < maxRetries) {
        const delay = Math.pow(2, retryCount) * 1000 + Math.random() * 1000;
        console.log(`Rate limit hit, retrying in ${delay}ms (attempt ${retryCount + 1}/${maxRetries})`);
        await new Promise(resolve => setTimeout(resolve, delay));
        return callSarvamChat(messages, temperature, maxTokens, retryCount + 1);
      } else {
        throw new Error('Rate limit exceeded after maximum retries');
      }
    }

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Sarvam API error response:', errorText);
      throw new Error(`Sarvam API error: ${response.status} - ${errorText}`);
    }

    const data = await response.json();
    if (!data.choices || !data.choices[0] || !data.choices[0].message || !data.choices[0].message.content) {
      throw new Error('No content received from Sarvam API');
    }

    return data.choices[0].message.content;
  } catch (error) {
    if (retryCount < 3 && (error as Error).message.includes('fetch')) {
      // Network error - retry with delay
      const delay = Math.pow(2, retryCount) * 1000;
      console.log(`Network error, retrying in ${delay}ms (attempt ${retryCount + 1}/3)`);
      await new Promise(resolve => setTimeout(resolve, delay));
      return callSarvamChat(messages, temperature, maxTokens, retryCount + 1);
    }
    throw error;
  }
}


async function rateLimitDelay(delayMs: number = 1000): Promise<void> {
  await new Promise(resolve => setTimeout(resolve, delayMs));
}

// Simple rate limit tracking
let lastApiCallTime = 0;
const MIN_INTERVAL_BETWEEN_CALLS = 1000;

async function makeRateLimitedApiCall<T>(apiCall: () => Promise<T>): Promise<T> {
  const now = Date.now();
  const timeSinceLastCall = now - lastApiCallTime;
  
  if (timeSinceLastCall < MIN_INTERVAL_BETWEEN_CALLS) {
    const waitTime = MIN_INTERVAL_BETWEEN_CALLS - timeSinceLastCall;
    await new Promise(resolve => setTimeout(resolve, waitTime));
  }
  
  lastApiCallTime = Date.now();
  return apiCall();
}

// Function to estimate token count (rough approximation: 1 token ≈ 4 characters)
function estimateTokenCount(text: string): number {
  return Math.ceil(text.length / 4);
}

// Function to chunk content into smaller pieces
function chunkContent(content: string, maxTokensPerChunk: number = 5000): string[] {
  const estimatedTokens = estimateTokenCount(content);
  
  if (estimatedTokens <= maxTokensPerChunk) {
    return [content];
  }
  
  const chunks: string[] = [];
  const sentences = content.match(/[^.!?]+[.!?]+/g) || [];
  
  let currentChunk = '';
  let currentTokens = 0;
  
  for (const sentence of sentences) {
    const sentenceTokens = estimateTokenCount(sentence);
    
    if (currentTokens + sentenceTokens > maxTokensPerChunk && currentChunk) {
      chunks.push(currentChunk.trim());
      currentChunk = sentence;
      currentTokens = sentenceTokens;
    } else {
      currentChunk += sentence;
      currentTokens += sentenceTokens;
    }
  }
  
  if (currentChunk.trim()) {
    chunks.push(currentChunk.trim());
  }
  
  return chunks;
}

// Function to summarize a chunk of content
async function summarizeChunk(chunk: string, chunkIndex: number, totalChunks: number): Promise<string> {
  const prompt = `You are a content summarizer. Please provide a comprehensive summary of the following content.
  
This is chunk ${chunkIndex + 1} of ${totalChunks} from a larger document.

Content to summarize:
${chunk}

Requirements:
- Create a detailed summary that captures all key points, concepts, and important technical details
- Maintain the technical accuracy and context
- Include specific examples, numbers, and data points mentioned
- Keep the summary comprehensive but concise
- Focus on the most important information that would be relevant for a podcast discussion

Provide only the summary without any additional formatting or explanations.`;

  try {
    const summary = await makeRateLimitedApiCall(() => 
      callSarvamChat([
        {
          role: 'user',
          content: prompt
        }
      ], 0.5, 4096)
    );

    if (!summary) {
      throw new Error(`No summary generated for chunk ${chunkIndex + 1}`);
    }

    return summary.trim();
  } catch (error) {
    console.error(`Error summarizing chunk ${chunkIndex + 1}:`, error);
    throw new Error(`Failed to summarize chunk ${chunkIndex + 1}: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// Function to process large content by chunking and summarizing
async function processLargeContent(content: string, title: string): Promise<string> {
  const maxTokensForScript = 4000; // Conservative limit to leave plenty of room for prompt overhead
  const estimatedTokens = estimateTokenCount(content);
  
  console.log(`Content estimated tokens: ${estimatedTokens}`);
  
  if (estimatedTokens <= maxTokensForScript) {
    console.log('Content fits within token limit, using original content');
    return content;
  }
  
  console.log('Content exceeds token limit, chunking and summarizing...');
  
  // Chunk the content
  const chunks = chunkContent(content, 4000);
  console.log(`Split content into ${chunks.length} chunks`);
  
  // Summarize each chunk
  const summaries: string[] = [];
  for (let i = 0; i < chunks.length; i++) {
    console.log(`Summarizing chunk ${i + 1}/${chunks.length}...`);
    try {
      const summary = await summarizeChunk(chunks[i], i, chunks.length);
      summaries.push(`Section ${i + 1}: ${summary}`);
      
      // Add delay between API calls to avoid rate limiting
      if (i < chunks.length - 1) {
        await rateLimitDelay(1500);
      }
    } catch (error) {
      console.error(`Failed to summarize chunk ${i + 1}, using original chunk (truncated)`);
      // Fallback: use truncated original chunk
      const truncated = chunks[i].substring(0, 2000) + '...';
      summaries.push(`Section ${i + 1}: ${truncated}`);
    }
  }
  
  // Combine summaries
  const combinedSummary = `Document: ${title}

The following is a comprehensive summary of the document organized by sections:

${summaries.join('\n\n')}`;
  
  console.log(`Combined summary tokens: ${estimateTokenCount(combinedSummary)}`);
  
  return combinedSummary;
}

async function generatePodcastScript(content: string, title: string, targetLanguage: string): Promise<ScriptSegment[]> {
  const languageNameForPrompt = LANGUAGE_PROMPT_NAMES[targetLanguage] || 'English'; // Default to English if no specific name found

  const languageInstruction = targetLanguage === 'en-IN' 
    ? 'Generate the script in English.'
    : `Generate the script in ${languageNameForPrompt}. Make sure the conversation flows naturally in that language.`;

  // Process content to handle large documents
  console.log('Processing content for script generation...');
  const processedContent = await processLargeContent(content, title);

  // Create the prompt template first to estimate its base size
  const promptTemplate = `You are a podcast script writer. Create an engaging 8-10 minute podcast conversation between two hosts discussing the following content. 

Content Title: ${title}
Content: CONTENT_PLACEHOLDER

Requirements:
- Create a natural, conversational dialogue between Host and Guest
- Include interesting insights and explain technical things in a simple way with examples, questions, and back-and-forth discussion
- Make it engaging and informative
- Keep each speaker turn to 1-3 sentences for natural flow
- Include natural transitions and reactions
- Create at least 10-15 dialog exchanges for a substantial conversation
- Total length should be appropriate for 8-10 minutes of speech
- ${languageInstruction}

IMPORTANT: You MUST return a valid JSON object with a "script" property containing an array. No markdown formatting, no code blocks, no backticks.

Format:
{
  "script": [
    {"speaker": "host", "text": "Welcome to our podcast! Today we're discussing..."},
    {"speaker": "guest", "text": "Thank you for having me. This is such an interesting topic because..."},
    {"speaker": "host", "text": "That's a great point. Can you elaborate on..."}
  ]
}`;

  // Calculate the base prompt tokens (without content)
  const basePromptTokens = estimateTokenCount(promptTemplate.replace('CONTENT_PLACEHOLDER', ''));
  const maxTotalTokens = 7000; // Leave some buffer under the 7168 limit
  const maxContentTokens = maxTotalTokens - basePromptTokens;

  console.log(`Base prompt tokens: ${basePromptTokens}, Max content tokens: ${maxContentTokens}`);

  // Truncate content if it's still too long
  let finalContent = processedContent;
  const contentTokens = estimateTokenCount(processedContent);
  
  if (contentTokens > maxContentTokens) {
    console.warn(`Content still too long (${contentTokens} tokens), truncating to ${maxContentTokens} tokens`);
    // Truncate to approximately the right character count (token count * 4)
    const maxCharacters = maxContentTokens * 4;
    finalContent = processedContent.substring(0, maxCharacters) + '\n\n[Content truncated due to length...]';
    console.log(`Content truncated to ${estimateTokenCount(finalContent)} tokens`);
  }

  const prompt = promptTemplate.replace('CONTENT_PLACEHOLDER', finalContent);
  const finalPromptTokens = estimateTokenCount(prompt);
  
  console.log(`Final prompt tokens: ${finalPromptTokens}`);
  
  if (finalPromptTokens > 7168) {
    throw new Error(`Prompt still too long after processing: ${finalPromptTokens} tokens (max: 7168)`);
  }

  try {
    const scriptText = await makeRateLimitedApiCall(() => 
      callSarvamChat([
        {
          role: 'user',
          content: prompt
        }
      ], 0.7, 8192)
    );

    if (!scriptText) {
      throw new Error('No script generated from Sarvam AI');
    }

    let cleanedText = scriptText.trim();
    if (cleanedText.startsWith('```json')) {
      cleanedText = cleanedText.replace(/^```json\s*/, '').replace(/\s*```$/, '');
    } else if (cleanedText.startsWith('```')) {
      cleanedText = cleanedText.replace(/^```\s*/, '').replace(/\s*```$/, '');
    }

    const parsed = JSON.parse(cleanedText);
    

    let script: ScriptSegment[];
    if (Array.isArray(parsed)) {
      script = parsed;
    } else if (parsed.script && Array.isArray(parsed.script)) {
      script = parsed.script;
    } else if (parsed.segments && Array.isArray(parsed.segments)) {
      script = parsed.segments;
    } else {
      throw new Error('Invalid script format received from Sarvam AI');
    }

    if (script.length < 5) {
      throw new Error('Generated script is too short - insufficient content for podcast');
    }

    if (script.length < 10) {
      console.warn('Script too short, adding more segments');
      const additionalSegments = [
        { speaker: 'host' as const, text: 'This really highlights some key insights from the content.' },
        { speaker: 'guest' as const, text: 'Absolutely, and I think this has broader implications for the field.' },
        { speaker: 'host' as const, text: 'What would you say are the most important takeaways for our listeners?' },
        { speaker: 'guest' as const, text: 'I\'d say the main points really center around practical applications.' },
        { speaker: 'host' as const, text: 'That\'s a great way to summarize it. Thank you for this insightful discussion.' }
      ];
      script = [...script, ...additionalSegments];
    }

    return script;
  } catch (error) {
    console.error('Error generating script:', error);
    throw new Error(`Failed to generate podcast script: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}


async function textToSpeech(text: string, language: string, speaker: 'host' | 'guest', retryCount: number = 0): Promise<string> {
  const apiKey = process.env.SARVAM_API_KEY;
  if (!apiKey) {
    throw new Error('Sarvam API key not configured');
  }

  const voices = VOICE_MAPPINGS[language] || VOICE_MAPPINGS['en-IN'];
  const selectedVoice = voices[speaker];

  try {
    const response = await fetch('https://api.sarvam.ai/text-to-speech', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'api-subscription-key': apiKey,
      },
      body: JSON.stringify({
        inputs: [text],
        target_language_code: language,
        speaker: selectedVoice,
        pitch: speaker === 'host' ? 0 : -0.1,
        pace: 1.0,
        loudness: 1.2,
        speech_sample_rate: 22050,
        enable_preprocessing: true,
        model: 'bulbul:v2'
      }),
    });

    if (response.status === 429) {
      const maxRetries = 3;
      if (retryCount < maxRetries) {
        const delay = Math.pow(2, retryCount) * 1000 + Math.random() * 1000;
        console.log(`TTS rate limit hit, retrying in ${delay}ms (attempt ${retryCount + 1}/${maxRetries})`);
        await new Promise(resolve => setTimeout(resolve, delay));
        return textToSpeech(text, language, speaker, retryCount + 1);
      } else {
        throw new Error('TTS rate limit exceeded after maximum retries');
      }
    }

    if (!response.ok) {
      const errorText = await response.text();
      console.error('TTS API error response:', errorText);
      throw new Error(`TTS API error: ${response.status} - ${errorText}`);
    }

    const data = await response.json();
    if (!data.audios || !data.audios[0]) {
      throw new Error('No audio data received from TTS API');
    }

    return data.audios[0];
  } catch (error) {
    if (retryCount < 3 && (error as Error).message.includes('fetch')) {
      const delay = Math.pow(2, retryCount) * 1000;
      console.log(`TTS network error, retrying in ${delay}ms (attempt ${retryCount + 1}/3)`);
      await new Promise(resolve => setTimeout(resolve, delay));
      return textToSpeech(text, language, speaker, retryCount + 1);
    }
    throw error;
  }
}

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