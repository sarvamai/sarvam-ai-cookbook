'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Loader2, Brain, FileText, Sparkles } from 'lucide-react';

interface ProcessingStatusProps {
  step: string;
}

export function ProcessingStatus({ step }: ProcessingStatusProps) {
  const getStepInfo = (step: string) => {
    if (step.includes('PDF') || step.includes('OCR')) {
      return {
        icon: FileText,
        title: 'Processing Document',
        description: 'Extracting text and analyzing content with Mistral OCR',
        progress: 25,
        color: 'text-blue-600'
      };
    }
    if (step.includes('script') || step.includes('Sarvam') || step.includes('audio') || step.includes('TTS')) {
      return {
        icon: Brain,
        title: 'Generating Content',
        description: 'Creating engaging podcast dialogue and converting to natural speech',
        progress: 75,
        color: 'text-purple-600'
      };
    }
    return {
      icon: Sparkles,
      title: 'Processing',
      description: 'Working on your podcast...',
      progress: 10,
      color: 'text-orange-600'
    };
  };

  const stepInfo = getStepInfo(step);
  const Icon = stepInfo.icon;

  return (
    <Card className="border-0 shadow-lg bg-gradient-to-r from-blue-950/20 to-purple-950/20">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-3">
          <div className="relative">
            <div className="absolute inset-0 animate-ping rounded-full bg-primary/20"></div>
            <div className={`relative rounded-full p-2 bg-background shadow-sm ${stepInfo.color}`}>
              <Icon className="h-5 w-5" />
            </div>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-lg font-semibold">{stepInfo.title}</span>
              <Badge variant="secondary" className="animate-pulse">
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Processing
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground font-normal mt-1">
              {stepInfo.description}
            </p>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-medium">{stepInfo.progress}%</span>
          </div>
          <Progress 
            value={stepInfo.progress} 
            className="h-2"
          />
        </div>
        
        <div className="flex items-center gap-2 p-3 bg-blue-950/10 rounded-lg">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">
            {step}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className={`flex items-center gap-2 p-2 rounded ${stepInfo.progress >= 25 ? 'bg-blue-900/30' : 'bg-blue-950/10'}`}>
            <FileText className={`h-4 w-4 ${stepInfo.progress >= 25 ? 'text-blue-400' : 'text-muted-foreground'}`} />
            <span className="text-xs font-medium">Document Processing</span>
          </div>
          <div className={`flex items-center gap-2 p-2 rounded ${stepInfo.progress >= 75 ? 'bg-purple-900/30' : 'bg-purple-950/10'}`}>
            <Brain className={`h-4 w-4 ${stepInfo.progress >= 75 ? 'text-purple-400' : 'text-muted-foreground'}`} />
            <span className="text-xs font-medium">Content Generation</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
} 