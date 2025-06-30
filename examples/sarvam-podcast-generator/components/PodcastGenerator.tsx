'use client';

import { useState } from 'react';
import { FileUpload } from './FileUpload';
import { PodcastControls } from './PodcastControls';
import { ProcessingStatus } from './ProcessingStatus';
import { LanguageSelector } from './LanguageSelector';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertCircle, Brain, FileText, Mic, Volume2, Clock, CheckCircle, XCircle } from 'lucide-react';
import { FaGithub, FaXTwitter, FaLinkedin } from 'react-icons/fa6';
import { pollJobStatus } from '@/lib/poll-job-status';

interface DocumentData {
  content: string;
  title: string;
  images?: Array<{ id: string; coordinates: { x: number; y: number; width: number; height: number } }>;
  metadata?: {
    model: string;
    pagesProcessed: number;
  };
}

interface PodcastData {
  audioSegments: Array<{ speaker: 'host' | 'guest'; text: string; audioUrl: string }>;
  transcript: string;
  script?: Array<{ speaker: 'host' | 'guest'; text: string }>;
  metadata?: {
    language: string;
    segmentCount: number;
    successfulAudioSegments: number;
    voices: { host: string; guest: string };
    duration: string;
    sessionId: string;
  };
}

interface JobStatus {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  result?: PodcastData;
  error?: string;
  createdAt: string;
  updatedAt: string;
}

export function PodcastGenerator() {
  const [documentData, setDocumentData] = useState<DocumentData | null>(null);
  const [podcastData, setPodcastData] = useState<PodcastData | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('hi-IN');
  const [error, setError] = useState<string | null>(null);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);

  const handleFileUpload = async (file: File) => {
    setIsProcessing(true);
    setError(null);
    setPodcastData(null);
    setJobStatus(null);
    setCurrentJobId(null);
    setProcessingStep('Processing PDF with Mistral OCR...');

    try {
      const formData = new FormData();
      formData.append('pdf', file);

      const parseResponse = await fetch('/api/parse-pdf', {
        method: 'POST',
        body: formData,
      });

      if (!parseResponse.ok) {
        const errorData = await parseResponse.json();
        throw new Error(errorData.error || 'Failed to parse PDF');
      }

      const parsedData = await parseResponse.json();
      setDocumentData({
        content: parsedData.content,
        title: file.name.replace('.pdf', ''),
        images: parsedData.images,
        metadata: parsedData.metadata
      });

      setProcessingStep('Starting podcast generation...');

      const podcastResponse = await fetch('/api/generate-podcast', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content: parsedData.content,
          language: selectedLanguage,
          title: file.name.replace('.pdf', ''),
        }),
      });

      if (!podcastResponse.ok) {
        const errorData = await podcastResponse.json();
        throw new Error(errorData.error || 'Failed to start podcast generation');
      }

      const jobResponse = await podcastResponse.json();
      setCurrentJobId(jobResponse.jobId);
      setProcessingStep('Podcast generation queued, waiting for processing...');

      const finalStatus = await pollJobStatus(
        jobResponse.jobId,
        (status: JobStatus) => {
          setJobStatus(status);

          switch (status.status) {
            case 'pending':
              setProcessingStep('Job queued, waiting to start...');
              break;
            case 'processing':
              setProcessingStep('Generating podcast script and audio...');
              break;
            case 'completed':
              setProcessingStep('Podcast generation completed!');
              break;
            case 'failed':
              setProcessingStep('Podcast generation failed');
              break;
          }
        }
      );

      if (finalStatus.status === 'completed' && finalStatus.result) {
        setPodcastData(finalStatus.result);
        setProcessingStep('Podcast ready!');
      } else if (finalStatus.status === 'failed') {
        throw new Error(finalStatus.error || 'Podcast generation failed');
      }

    } catch (error) {
      console.error('Error processing file:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      setError(errorMessage);
    } finally {
      setIsProcessing(false);
      setProcessingStep('');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'processing':
        return <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-blue-950 to-indigo-950">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-indigo-600 bg-clip-text text-transparent mb-4">
            AI Podcast Generator
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            Transform your PDF documents into engaging AI-powered podcasts using Sarvam M model for script generation and Sarvam Bulbul-V2 TTS for text-to-speech and Mistral OCR for PDF parsing
          </p>
          <div className="flex items-center justify-center gap-4 mt-6">
            <Badge variant="secondary" className="text-sm">
              <Brain className="w-4 h-4 mr-1" />
              Sarvam M
            </Badge>
            <Badge variant="secondary" className="text-sm">
              <FileText className="w-4 h-4 mr-1" />
              Mistral OCR
            </Badge>
            <Badge variant="secondary" className="text-sm">
              <Volume2 className="w-4 h-4 mr-1" />
              Bulbul-V2 TTS
            </Badge>
          </div>
        </div>

        {/* Language Selection */}
        <Card className="mb-8 border-0 shadow-lg">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2">
              <Mic className="w-5 h-5" />
              Language Settings
            </CardTitle>
            <CardDescription>Choose your preferred language for podcast generation</CardDescription>
          </CardHeader>
          <CardContent>
            <LanguageSelector
              selectedLanguage={selectedLanguage}
              onLanguageChange={setSelectedLanguage}
            />
          </CardContent>
        </Card>

        {/* Error Display */}
        {error && (
          <Alert variant="destructive" className="mb-8">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="font-medium">
              {error}
            </AlertDescription>
          </Alert>
        )}

        {/* Job Status Display */}
        {jobStatus && (
          <Card className="mb-8 border-0 shadow-lg">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2">
                {getStatusIcon(jobStatus.status)}
                Job Status
              </CardTitle>
              <CardDescription>
                Job ID: {jobStatus.id}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Status:</span>
                  <Badge
                    variant={
                      jobStatus.status === 'completed' ? 'default' :
                        jobStatus.status === 'failed' ? 'destructive' :
                          jobStatus.status === 'processing' ? 'secondary' : 'outline'
                    }
                  >
                    {jobStatus.status.charAt(0).toUpperCase() + jobStatus.status.slice(1)}
                  </Badge>
                </div>
                <div className="text-sm text-muted-foreground">
                  Last updated: {new Date(jobStatus.updatedAt).toLocaleTimeString()}
                </div>
              </div>
              {jobStatus.error && (
                <Alert variant="destructive" className="mt-4">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    {jobStatus.error}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
          {/* Left Column */}
          <div className="space-y-8">
            {/* Upload Section */}
            <Card className="border-0 shadow-lg">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="w-5 h-5" />
                  Document Upload
                </CardTitle>
                <CardDescription>
                  Upload your PDF document to get started with podcast generation
                </CardDescription>
              </CardHeader>
              <CardContent>
                <FileUpload onFileUpload={handleFileUpload} />
              </CardContent>
            </Card>

            {/* Document Preview */}
            {documentData && (
              <Card className="border-0 shadow-lg">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <FileText className="w-5 h-5" />
                      Document Analysis
                    </div>
                    <Badge variant="outline" className="ml-auto">
                      {documentData.metadata?.pagesProcessed} pages
                    </Badge>
                  </CardTitle>
                  <CardDescription>{documentData.title}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Document metadata */}
                  {documentData.metadata && (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="flex items-center gap-2">
                        <Brain className="w-4 h-4 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">OCR Model:</span>
                        <Badge variant="secondary" className="text-xs">
                          {documentData.metadata.model}
                        </Badge>
                      </div>
                      {documentData.images && (
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">Images:</span>
                          <Badge variant="outline" className="text-xs">
                            {documentData.images.length}
                          </Badge>
                        </div>
                      )}
                    </div>
                  )}

                  <Separator />

                  <div>
                    <h4 className="text-sm font-medium mb-2">Content Preview</h4>
                    <ScrollArea className="h-32 w-full rounded-md border bg-muted/30 p-3">
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {documentData.content.substring(0, 500)}
                        {documentData.content.length > 500 && '...'}
                      </p>
                    </ScrollArea>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right Column */}
          <div className="space-y-8">
            {/* Processing Status */}
            {isProcessing && (
              <ProcessingStatus step={processingStep} />
            )}

            {/* Generated Podcast */}
            {podcastData && (
              <Card className="border-0 shadow-lg">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Mic className="w-5 h-5" />
                    Generated Podcast
                  </CardTitle>
                  <CardDescription>
                    Your AI-generated podcast is ready to play
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Podcast metadata */}
                  {podcastData.metadata && (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-muted-foreground">Language</span>
                          <Badge variant="secondary">
                            {podcastData.metadata.language}
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-muted-foreground">Duration</span>
                          <Badge variant="outline">
                            {podcastData.metadata.duration}
                          </Badge>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-muted-foreground">Segments</span>
                          <Badge variant="secondary">
                            {podcastData.metadata.successfulAudioSegments}/{podcastData.metadata.segmentCount}
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-muted-foreground">Voices</span>
                          <div className="flex gap-1">
                            <Badge variant="outline" className="text-xs">
                              {podcastData.metadata.voices.host}
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              {podcastData.metadata.voices.guest}
                            </Badge>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <Separator />

                  {/* Podcast Controls */}
                  <PodcastControls
                    audioSegments={podcastData.audioSegments}
                    transcript={podcastData.transcript}
                  />

                  {/* Script Preview */}
                  {podcastData.script && (
                    <div className="mt-6">
                      <Tabs defaultValue="script" className="w-full">
                        <TabsList className="grid w-full grid-cols-2">
                          <TabsTrigger value="script">Script Preview</TabsTrigger>
                          <TabsTrigger value="transcript">Full Transcript</TabsTrigger>
                        </TabsList>
                        <TabsContent value="script">
                          <ScrollArea className="h-48 w-full rounded-md border bg-muted/30 p-4">
                            <div className="space-y-4">
                              {podcastData.script.slice(0, 5).map((segment, index) => (
                                <div key={index} className="space-y-1">
                                  <Badge
                                    variant={segment.speaker === 'host' ? 'default' : 'secondary'}
                                    className="text-xs"
                                  >
                                    {segment.speaker.toUpperCase()}
                                  </Badge>
                                  <p className="text-sm leading-relaxed pl-2">
                                    {segment.text}
                                  </p>
                                </div>
                              ))}
                              {podcastData.script.length > 5 && (
                                <p className="text-xs text-muted-foreground text-center pt-2">
                                  ... and {podcastData.script.length - 5} more segments
                                </p>
                              )}
                            </div>
                          </ScrollArea>
                        </TabsContent>
                        <TabsContent value="transcript">
                          <ScrollArea className="h-48 w-full rounded-md border bg-muted/30 p-4">
                            <p className="text-sm leading-relaxed whitespace-pre-wrap">
                              {podcastData.transcript}
                            </p>
                          </ScrollArea>
                        </TabsContent>
                      </Tabs>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-16 py-8 border-t border-border/50">
          <div className="text-center space-y-4">
            <p className="text-muted-foreground">
              Made with <span>❤️</span> by{' '}
              <span className="font-semibold text-foreground">Amey Muke</span>
            </p>
            <div className="flex items-center justify-center gap-6">
              <a
                href="https://github.com/perfect7613"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors duration-200 hover:scale-105 transform"
              >
                <FaGithub className="w-5 h-5" aria-hidden="true" />
                <span className="text-sm">GitHub</span>
              </a>
              <a
                href="https://www.linkedin.com/in/amey-muke-065456205/"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors duration-200 hover:scale-105 transform"
              >
                <FaLinkedin className="w-5 h-5" aria-hidden="true" />
                <span className="text-sm">LinkedIn</span>
              </a>
              <a
                href="https://x.com/7613Perfect"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors duration-200 hover:scale-105 transform"
              >
                <FaXTwitter className="w-5 h-5" aria-hidden="true" />
                <span className="text-sm">X</span>
              </a>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
} 