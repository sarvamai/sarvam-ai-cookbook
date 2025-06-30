'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Play, 
  Pause, 
  SkipBack, 
  SkipForward, 
  Volume2, 
  Download,
  FileText,
  Mic,
  UserCircle,
  Loader2,
  AlertCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface AudioSegment {
  speaker: 'host' | 'guest';
  text: string;
  audioUrl: string;
}

interface PodcastControlsProps {
  audioSegments: AudioSegment[];
  transcript: string;
}

interface PreloadedSegment extends AudioSegment {
  startTime: number;
  endTime: number;
  duration: number;
  audioElement: HTMLAudioElement;
  isLoaded: boolean;
}

export function PodcastControls({ audioSegments, transcript }: PodcastControlsProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentSegment, setCurrentSegment] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [preloadProgress, setPreloadProgress] = useState(0);
  const [isPreloading, setIsPreloading] = useState(false);
  const preloadedSegmentsRef = useRef<PreloadedSegment[]>([]);
  const totalDurationRef = useRef(0);

  const validSegments = useMemo(() => {
    return audioSegments.filter(segment => segment.audioUrl);
  }, [audioSegments]);

  useEffect(() => {
    if (validSegments.length === 0) return;
    
    const preloadAllSegments = async () => {
      setIsPreloading(true);
      setPreloadProgress(0);
      setError(null);
      
      try {
        const preloadedSegments: PreloadedSegment[] = [];
        let cumulativeTime = 0;
        
        const segmentsToProcess = await Promise.all(
          validSegments.map(async (segment, index) => {
            if (segment.audioUrl.includes('uploadthing.com') || segment.audioUrl.includes('utfs.io')) {
              let retryCount = 0;
              const maxRetries = index === 0 ? 5 : 3;
              
              while (retryCount < maxRetries) {
                try {
                  const response = await fetch(segment.audioUrl);
                  if (!response.ok) {
                    throw new Error(`Failed to fetch from UploadThing: ${response.status}`);
                  }
                  const dataUrl = await response.text();
                  if (!dataUrl.startsWith('data:audio/')) {
                    throw new Error('Invalid data URL format received');
                  }
                  return { ...segment, audioUrl: dataUrl };
                } catch (error) {
                  retryCount++;
                  const isFirstSegment = index === 0;
                  const delayMs = isFirstSegment ? 2000 * retryCount : 1000 * retryCount; // Longer delays for first segment
                  
                  if (retryCount < maxRetries) {
                    await new Promise(resolve => setTimeout(resolve, delayMs));
                  } else {
                    console.error(`Failed to fetch data URL for segment ${index + 1} after ${maxRetries} attempts. Using original URL as fallback.`);
                    return segment;
                  }
                }
              }
            }
            return segment;
          })
        );
        
        for (let i = 0; i < segmentsToProcess.length; i++) {
          const segment = segmentsToProcess[i];
          const audioElement = new Audio();
          
          // Set up audio element properties
          audioElement.preload = 'auto';
          audioElement.volume = 1.0;
          
          // Give first segment highest priority
          if (i === 0) {
            audioElement.preload = 'auto';
            // For the first segment, try to establish connection early
            if (!segment.audioUrl.startsWith('data:')) {
              audioElement.crossOrigin = 'anonymous';
              // Pre-warm the connection for first segment
              const link = document.createElement('link');
              link.rel = 'preload';
              link.as = 'audio';
              link.href = segment.audioUrl;
              document.head.appendChild(link);
              setTimeout(() => document.head.removeChild(link), 5000);
            }
          } else {
            // Don't set crossOrigin for data URLs (base64)
            if (!segment.audioUrl.startsWith('data:')) {
              audioElement.crossOrigin = 'anonymous';
            }
          }
          
          // Wait for audio to load with proper sequencing
          await new Promise<void>((resolve, reject) => {
            let resolved = false;
            let timeoutId: NodeJS.Timeout;
            
            const cleanup = () => {
              if (resolved) return;
              resolved = true;
              clearTimeout(timeoutId);
              audioElement.removeEventListener('loadedmetadata', handleLoadedMetadata);
              audioElement.removeEventListener('canplaythrough', handleCanPlayThrough);
              audioElement.removeEventListener('error', handleError);
            };
            
            const handleLoadedMetadata = () => {
              const segmentDuration = isFinite(audioElement.duration) && audioElement.duration > 0 
                ? audioElement.duration 
                : 3; // Default 3 seconds if duration is invalid
              
              preloadedSegments.push({
                ...segment,
                startTime: cumulativeTime,
                endTime: cumulativeTime + segmentDuration,
                duration: segmentDuration,
                audioElement,
                isLoaded: true
              });
              
              cumulativeTime += segmentDuration;
              setPreloadProgress(((i + 1) / segmentsToProcess.length) * 100);
              
              cleanup();
              resolve();
            };
            
            const handleCanPlayThrough = () => {
              if (!resolved && audioElement.readyState >= HTMLMediaElement.HAVE_ENOUGH_DATA) {
                handleLoadedMetadata();
              }
            };
            
            const handleError = (e: any) => {
              // Create a fallback segment but still mark as loaded for playback
              // We'll handle the actual loading during playback if needed
              const fallbackSegment = {
                ...segment,
                startTime: cumulativeTime,
                endTime: cumulativeTime + 3,
                duration: 3,
                audioElement: new Audio(),
                isLoaded: true
              };
              
              fallbackSegment.audioElement.src = segment.audioUrl;
              fallbackSegment.audioElement.preload = 'none';
              
              preloadedSegments.push(fallbackSegment);
              cumulativeTime += 3;
              setPreloadProgress(((i + 1) / segmentsToProcess.length) * 100);
              
              cleanup();
              resolve();
            };
            
            audioElement.addEventListener('loadedmetadata', handleLoadedMetadata);
            audioElement.addEventListener('canplaythrough', handleCanPlayThrough);
            audioElement.addEventListener('error', handleError);
            
            const timeoutDuration = i === 0 ? 30000 : (i === 1 ? 25000 : 20000);
            timeoutId = setTimeout(() => {
              if (!resolved) {
                handleError(new Error('Timeout'));
              }
            }, timeoutDuration);
            
            // Start loading
            audioElement.src = segment.audioUrl;
            audioElement.load();
          });
        }
        
        preloadedSegmentsRef.current = preloadedSegments;
        totalDurationRef.current = cumulativeTime;
        setDuration(cumulativeTime);
        setIsPreloading(false);
        
      } catch (error) {
        console.error('Error during preloading:', error);
        
        // Enhanced fallback: create segments with basic audio elements but mark as loaded
        const fallbackSegments: PreloadedSegment[] = validSegments.map((segment, i) => {
          const audioElement = new Audio();
          audioElement.src = segment.audioUrl;
          audioElement.preload = 'none';
          
          return {
            ...segment,
            startTime: i * 5,
            endTime: (i + 1) * 5,
            duration: 5,
            audioElement,
            isLoaded: true // Mark as loaded so they don't get skipped
          };
        });
        
        preloadedSegmentsRef.current = fallbackSegments;
        totalDurationRef.current = validSegments.length * 5;
        setDuration(validSegments.length * 5);
        setIsPreloading(false);
        setError('Using basic playback mode - segments will load individually');
      }
    };
    
    preloadAllSegments();
    
    // Enhanced cleanup function
    return () => {
      preloadedSegmentsRef.current.forEach((segment, index) => {
        if (segment.audioElement) {
          try {
            segment.audioElement.pause();
            segment.audioElement.currentTime = 0;
            segment.audioElement.src = '';
            segment.audioElement.load(); // Reset the audio element
          } catch (e) {
            console.warn(`Error cleaning up audio element ${index}:`, e);
          }
        }
      });
      preloadedSegmentsRef.current = [];
      totalDurationRef.current = 0;
    };
  }, [validSegments]);

  // Get current segment based on playback time
  const getCurrentSegmentIndex = (time: number): number => {
    const segments = preloadedSegmentsRef.current;
    for (let i = 0; i < segments.length; i++) {
      if (time >= segments[i].startTime && time < segments[i].endTime) {
        return i;
      }
    }
    return Math.max(0, segments.length - 1);
  };

  // Seamless playback system using preloaded segments
  useEffect(() => {
    if (preloadedSegmentsRef.current.length === 0 || isPreloading) return;

    let currentAudio: HTMLAudioElement | null = null;
    let playbackStartTime = 0;
    let animationFrame: number;
    let isPlaybackActive = false;

    const updateProgress = () => {
      if (!currentAudio || !isPlaying || !isPlaybackActive) return;

      const elapsed = currentAudio.currentTime;
      const totalElapsed = playbackStartTime + elapsed;
      
      if (Math.abs(totalElapsed - currentTime) > 0.1) {
        setCurrentTime(totalElapsed);
      }

      animationFrame = requestAnimationFrame(updateProgress);
    };

    const playSegment = async (segmentIndex: number, startOffset: number = 0) => {
      if (segmentIndex >= preloadedSegmentsRef.current.length) {
        setIsPlaying(false);
        return;
      }

      const segment = preloadedSegmentsRef.current[segmentIndex];
      if (!segment) {
        setIsPlaying(false);
        return;
      }

      let audioToPlay = segment.audioElement;
      
      try {
        audioToPlay.pause();
        audioToPlay.currentTime = 0;
      } catch (e) {
        console.error('Error pausing audio:', e);
      }
      
      if (!audioToPlay.src || audioToPlay.readyState === HTMLMediaElement.HAVE_NOTHING) {
        audioToPlay.src = segment.audioUrl;
        audioToPlay.preload = 'auto';
        audioToPlay.volume = 1.0;
        
        // Don't set crossOrigin for data URLs (base64)
        if (!segment.audioUrl.startsWith('data:')) {
          audioToPlay.crossOrigin = 'anonymous';
        }
      }

      // Wait for the audio to be ready to play with proper sequencing
      if (audioToPlay.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
        try {
          await new Promise<void>((resolve, reject) => {
            const timeoutDuration = segmentIndex === 0 ? 20000 : 15000; // More time for first segment during playback
            const timeoutId = setTimeout(() => {
              reject(new Error('Load timeout during playback'));
            }, timeoutDuration);
            
            const handleCanPlay = () => {
              clearTimeout(timeoutId);
              audioToPlay.removeEventListener('canplay', handleCanPlay);
              audioToPlay.removeEventListener('loadeddata', handleCanPlay);
              audioToPlay.removeEventListener('error', handleError);
              resolve();
            };
            
            const handleError = (e: any) => {
              clearTimeout(timeoutId);
              audioToPlay.removeEventListener('canplay', handleCanPlay);
              audioToPlay.removeEventListener('loadeddata', handleCanPlay);
              audioToPlay.removeEventListener('error', handleError);
              reject(e);
            };
            
            audioToPlay.addEventListener('canplay', handleCanPlay);
            audioToPlay.addEventListener('loadeddata', handleCanPlay);
            audioToPlay.addEventListener('error', handleError);
            
            if (audioToPlay.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
              handleCanPlay();
            } else {
              if (audioToPlay.networkState !== HTMLMediaElement.NETWORK_LOADING) {
                audioToPlay.load();
              }
            }
          });
        } catch (error) {
          // Try to move to next segment
          if (segmentIndex < preloadedSegmentsRef.current.length - 1) {
            const nextSegmentIndex = segmentIndex + 1;
            setCurrentSegment(nextSegmentIndex);
            setTimeout(() => playSegment(nextSegmentIndex, 0), 100);
          } else {
            setIsPlaying(false);
          }
          return;
        }
      }

      currentAudio = audioToPlay;
      
      // Reset audio element state with proper error handling
      try {
        const targetTime = Math.max(0, Math.min(startOffset, currentAudio.duration || 0));
        if (isFinite(targetTime)) {
          currentAudio.currentTime = targetTime;
        } else {
          currentAudio.currentTime = 0;
        }
      } catch (e) {
        try {
          currentAudio.currentTime = 0;
        } catch (e2) {
          console.error('Error setting current time:', e2);
        }
      }
      
      await new Promise(resolve => setTimeout(resolve, 50));
      
      try {
        if (currentAudio.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
          await new Promise<void>((resolve) => {
            const handleReady = () => {
              currentAudio?.removeEventListener('canplay', handleReady);
              resolve();
            };
            currentAudio?.addEventListener('canplay', handleReady);
            // Fallback timeout
            setTimeout(resolve, 2000);
          });
        }
        
        // Ensure we're not already playing to avoid conflicts
        if (!currentAudio.paused) {
          try {
            currentAudio.pause();
            await new Promise(resolve => setTimeout(resolve, 10));
          } catch (e) {
            console.error('Error pausing audio:', e);
          }
        }
        
        const playPromise = currentAudio.play();
        
        // Handle the play promise properly
        if (playPromise !== undefined) {
          await playPromise;
        }
        
        isPlaybackActive = true;
        
        // Start continuous progress updates
        updateProgress();
        
        const handleEnded = () => {
          if (currentAudio) {
            currentAudio.removeEventListener('ended', handleEnded);
            currentAudio.removeEventListener('error', handlePlayError);
          }
          
          // Stop current progress updates
          cancelAnimationFrame(animationFrame);
          
          // Move to next segment
          if (segmentIndex < preloadedSegmentsRef.current.length - 1) {
            playbackStartTime = segment.endTime;
            const nextSegmentIndex = segmentIndex + 1;
            setCurrentSegment(nextSegmentIndex);
            // Small delay to ensure state updates
            setTimeout(() => playSegment(nextSegmentIndex, 0), 100);
          } else {
            // Podcast finished
            setIsPlaying(false);
            setCurrentSegment(0);
            setCurrentTime(0);
            playbackStartTime = 0;
            isPlaybackActive = false;
          }
        };

        const handlePlayError = (e: any) => {
          if (currentAudio) {
            currentAudio.removeEventListener('ended', handleEnded);
            currentAudio.removeEventListener('error', handlePlayError);
          }
          
          // Stop current progress updates
          cancelAnimationFrame(animationFrame);
          
          // Try next segment
          if (segmentIndex < preloadedSegmentsRef.current.length - 1) {
            const nextSegmentIndex = segmentIndex + 1;
            setCurrentSegment(nextSegmentIndex);
            setTimeout(() => playSegment(nextSegmentIndex, 0), 100);
          } else {
            setError('Playback error - please try again');
            setIsPlaying(false);
            isPlaybackActive = false;
          }
        };

        currentAudio.addEventListener('ended', handleEnded);
        currentAudio.addEventListener('error', handlePlayError);
        
      } catch (error) {
        if (error instanceof Error && error.message.includes('interrupted')) {
          setTimeout(() => playSegment(segmentIndex, startOffset), 200);
          return;
        }
        
        // Try to move to next segment instead of stopping completely
        if (segmentIndex < preloadedSegmentsRef.current.length - 1) {
          const nextSegmentIndex = segmentIndex + 1;
          setCurrentSegment(nextSegmentIndex);
          setTimeout(() => playSegment(nextSegmentIndex, 0), 100);
        } else {
          setError(`Error playing segment ${segmentIndex + 1}`);
          setIsPlaying(false);
          isPlaybackActive = false;
        }
      }
    };

    const pauseCurrentSegment = () => {
      isPlaybackActive = false;
      cancelAnimationFrame(animationFrame);
      
      if (currentAudio) {
        try {
          // Only pause if it's actually playing to avoid unnecessary operations
          if (!currentAudio.paused) {
            currentAudio.pause();
          }
        } catch (e) {
          console.warn('Error pausing audio:', e);
        }
      }
    };

    if (isPlaying && !isPlaybackActive) {
      // Calculate which segment to play and at what offset
      const targetTime = currentTime;
      const segmentIndex = getCurrentSegmentIndex(targetTime);
      const segment = preloadedSegmentsRef.current[segmentIndex];
      
      if (segment) {
        const segmentOffset = Math.max(0, targetTime - segment.startTime);
        playbackStartTime = segment.startTime;
        setCurrentSegment(segmentIndex);
        playSegment(segmentIndex, segmentOffset);
      } else {
        // Fallback to start from the beginning
        setCurrentTime(0);
        setCurrentSegment(0);
        playbackStartTime = 0;
        if (preloadedSegmentsRef.current.length > 0) {
          playSegment(0, 0);
        }
      }
    } else if (!isPlaying) {
      pauseCurrentSegment();
    }

    return () => {
      pauseCurrentSegment();
      if (currentAudio) {
        currentAudio.removeEventListener('ended', () => {});
        currentAudio.removeEventListener('error', () => {});
      }
      isPlaybackActive = false;
    };
  }, [isPlaying, isPreloading]);

  const handlePlayPause = async () => {
    if (preloadedSegmentsRef.current.length === 0 || isPreloading) {
      return;
    }

    const wasPlaying = isPlaying;
    setIsPlaying(!isPlaying);
    
    if (!wasPlaying) {
      // Starting playback
      // If we're at the very beginning (time 0 and segment 0), ensure we start from the first segment
      if (currentTime === 0 && currentSegment === 0) {
        // Make sure we're set to play the first segment
        setCurrentTime(0);
        setCurrentSegment(0);
      }
    } else {
    }
  };

  const handlePrevious = () => {
    if (currentSegment > 0) {
      const prevSegment = preloadedSegmentsRef.current[currentSegment - 1];
      if (prevSegment) {
        // Pause current playback before switching
        const wasPlaying = isPlaying;
        if (wasPlaying) {
          setIsPlaying(false);
        }
        
        setTimeout(() => {
          setCurrentTime(prevSegment.startTime);
          setCurrentSegment(currentSegment - 1);
          
          // Resume playback if it was playing
          if (wasPlaying) {
            setIsPlaying(true);
          }
        }, 100);
      }
    }
  };

  const handleNext = () => {
    if (currentSegment < preloadedSegmentsRef.current.length - 1) {
      const nextSegment = preloadedSegmentsRef.current[currentSegment + 1];
      if (nextSegment) {
        // Pause current playback before switching
        const wasPlaying = isPlaying;
        if (wasPlaying) {
          setIsPlaying(false);
        }
        
        setTimeout(() => {
          setCurrentTime(nextSegment.startTime);
          setCurrentSegment(currentSegment + 1);
          
          // Resume playback if it was playing
          if (wasPlaying) {
            setIsPlaying(true);
          }
        }, 100);
      }
    }
  };

  const handleSeek = (value: number[]) => {
    if (totalDurationRef.current > 0) {
      const seekTime = (value[0] / 100) * totalDurationRef.current;
      
      // Pause current playback before seeking
      if (isPlaying) {
        setIsPlaying(false);
        // Give a small delay to ensure current playback is stopped
        setTimeout(() => {
          setCurrentTime(seekTime);
          
          // Update current segment based on seek time
          const newSegmentIndex = getCurrentSegmentIndex(seekTime);
          setCurrentSegment(newSegmentIndex);
          
          // Resume playback after seek
          setIsPlaying(true);
        }, 100);
      } else {
        setCurrentTime(seekTime);
        
        // Update current segment based on seek time
        const newSegmentIndex = getCurrentSegmentIndex(seekTime);
        setCurrentSegment(newSegmentIndex);
      }
    }
  };

  const formatTime = (time: number) => {
    if (isNaN(time)) return '0:00';
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const downloadSegment = async (segment: AudioSegment, index: number) => {
    try {
      // First, try to get the processed URL from preloaded segments
      let audioUrl = segment.audioUrl;
      const preloadedSegment = preloadedSegmentsRef.current[index];
      if (preloadedSegment && preloadedSegment.audioUrl) {
        audioUrl = preloadedSegment.audioUrl;
      }
      
      // If it's still an UploadThing URL, fetch the actual data URL
      if (audioUrl.includes('uploadthing.com') || audioUrl.includes('utfs.io')) {
        try {
          const response = await fetch(audioUrl);
          if (response.ok) {
            const dataUrl = await response.text();
            if (dataUrl.startsWith('data:audio/')) {
              audioUrl = dataUrl;
            }
          }
        } catch (e) {
          console.error('Failed to fetch UploadThing URL for download:', e);
        }
      }
      
      let downloadUrl = audioUrl;
      let shouldRevoke = false;
      
      // If it's a base64 data URL, convert it to a blob URL for download
      if (audioUrl.startsWith('data:audio/')) {
        const byteCharacters = atob(audioUrl.split(',')[1]);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'audio/mpeg' });
        downloadUrl = URL.createObjectURL(blob);
        shouldRevoke = true;
      }
      
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `segment-${index + 1}-${segment.speaker}.mp3`;
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      // Clean up blob URL if we created one
      if (shouldRevoke) {
        setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
      }
    } catch (error) {
      console.error('Error downloading segment:', error);
      // Fallback: try direct download with original URL
      const link = document.createElement('a');
      link.href = segment.audioUrl;
      link.download = `segment-${index + 1}-${segment.speaker}.mp3`;
      link.target = '_blank';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const currentSegmentData = preloadedSegmentsRef.current[currentSegment] || validSegments[currentSegment];
  const progressPercentage = totalDurationRef.current > 0 ? (currentTime / totalDurationRef.current) * 100 : 0;

  return (
    <div className="space-y-6">
      
      {/* Main Player Card */}
      <Card className="border-0 shadow-lg bg-gradient-to-r from-blue-950/20 to-purple-950/20">
        <CardContent className="p-6 space-y-6">
          {/* Preloading Indicator */}
          {isPreloading && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Loading audio segments...</span>
                <span className="text-sm text-muted-foreground">{Math.round(preloadProgress)}%</span>
              </div>
              <Progress value={preloadProgress} className="h-2" />
            </div>
          )}

          {/* Current Segment Info */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {currentSegmentData && !isPreloading && (
                <>
                  <div className={cn(
                    "p-2 rounded-full",
                    currentSegmentData.speaker === 'host' 
                      ? "bg-blue-900/30 text-blue-400"
                      : "bg-purple-900/30 text-purple-400"
                  )}>
                    <UserCircle className="h-5 w-5" />
                  </div>
                  <div>
                    <Badge 
                      variant={currentSegmentData.speaker === 'host' ? 'default' : 'secondary'}
                      className="mb-1"
                    >
                      {currentSegmentData.speaker.toUpperCase()}
                    </Badge>
                    <p className="text-sm text-muted-foreground">
                      Segment {currentSegment + 1} of {preloadedSegmentsRef.current.length || validSegments.length}
                    </p>
                  </div>
                </>
              )}
              {isPreloading && (
                <div className="flex items-center gap-2">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Preparing seamless playback...</span>
                </div>
              )}
            </div>
            
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-xs">
                <Volume2 className="h-3 w-3 mr-1" />
                {formatTime(currentTime)} / {formatTime(totalDurationRef.current || duration)}
              </Badge>
            </div>
          </div>

          {/* Progress Bar */}
          {!isPreloading && (
            <div className="space-y-2">
              <Progress
                value={progressPercentage}
                max={100}
                className="h-2"
                onClick={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  const clickX = e.clientX - rect.left;
                  const percentage = (clickX / rect.width) * 100;
                  handleSeek([percentage]);
                }}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{formatTime(currentTime)}</span>
                <span>{formatTime(totalDurationRef.current || duration)}</span>
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="flex items-center justify-center gap-4">
            <Button
              variant="outline"
              size="icon"
              onClick={handlePrevious}
              disabled={currentSegment === 0 || isPreloading}
              className="h-12 w-12"
            >
              <SkipBack className="h-5 w-5" />
            </Button>

            <Button
              size="lg"
              onClick={handlePlayPause}
              disabled={validSegments.length === 0 || isPreloading}
              className="h-16 w-16 rounded-full"
            >
              {isPreloading ? (
                <Loader2 className="h-6 w-6 animate-spin" />
              ) : isPlaying ? (
                <Pause className="h-6 w-6" />
              ) : (
                <Play className="h-6 w-6 ml-1" />
              )}
            </Button>

            <Button
              variant="outline"
              size="icon"
              onClick={handleNext}
              disabled={currentSegment === preloadedSegmentsRef.current.length - 1 || isPreloading}
              className="h-12 w-12"
            >
              <SkipForward className="h-5 w-5" />
            </Button>
          </div>

          {/* Current Segment Text */}
          {currentSegmentData && (
            <Card className="bg-muted/30">
              <CardContent className="p-4">
                <p className="text-sm leading-relaxed">
                  {currentSegmentData.text}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Error Display */}
          {error && (
            <Card className="border-destructive/50 bg-destructive/5">
              <CardContent className="p-4 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-destructive" />
                <span className="text-sm text-destructive">{error}</span>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>

      {/* Podcast Details */}
      <Tabs defaultValue="segments" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="segments">Audio Segments</TabsTrigger>
          <TabsTrigger value="transcript">Full Transcript</TabsTrigger>
          <TabsTrigger value="download">Download</TabsTrigger>
        </TabsList>

        <TabsContent value="segments">
          <Card>
            <CardContent className="p-0">
              <ScrollArea className="h-80">
                <div className="p-4 space-y-4">
                  {validSegments.map((segment, index) => (
                    <div
                      key={index}
                      className={cn(
                        "flex items-start gap-3 p-4 rounded-lg border transition-colors cursor-pointer",
                        index === currentSegment 
                          ? "bg-primary/5 border-primary/20" 
                          : "hover:bg-muted/50"
                      )}
                      onClick={() => setCurrentSegment(index)}
                    >
                      <div className={cn(
                        "p-2 rounded-full mt-1",
                        segment.speaker === 'host' 
                          ? "bg-blue-900/30 text-blue-400"
                          : "bg-purple-900/30 text-purple-400"
                      )}>
                        <Mic className="h-4 w-4" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge 
                            variant={segment.speaker === 'host' ? 'default' : 'secondary'}
                            className="text-xs"
                          >
                            {segment.speaker.toUpperCase()}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            Segment {index + 1}
                          </span>
                          {index === currentSegment && (
                            <Badge variant="outline" className="text-xs">
                              Now Playing
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm leading-relaxed">
                          {segment.text}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={async (e) => {
                          e.stopPropagation();
                          await downloadSegment(segment, index);
                        }}
                        className="h-8 w-8"
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="transcript">
          <Card>
            <CardContent className="p-0">
              <ScrollArea className="h-80">
                <div className="p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <FileText className="h-5 w-5" />
                    <h3 className="font-semibold">Complete Transcript</h3>
                  </div>
                  <div className="prose prose-sm max-w-none dark:prose-invert">
                    <p className="whitespace-pre-wrap leading-relaxed">
                      {transcript}
                    </p>
                  </div>
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="download">
          <Card>
            <CardContent className="p-6 space-y-4">
              <div className="flex items-center gap-2 mb-4">
                <Download className="h-5 w-5" />
                <h3 className="font-semibold">Download Options</h3>
              </div>
              
              <div className="grid gap-3">
                <Button variant="outline" className="justify-start">
                  <Download className="h-4 w-4 mr-2" />
                  Download Complete Podcast (ZIP)
                </Button>
                
                <Separator />
                
                <p className="text-sm text-muted-foreground">Individual Segments:</p>
                
                {validSegments.map((segment, index) => (
                  <Button
                    key={index}
                    variant="ghost"
                    className="justify-between"
                    onClick={async () => await downloadSegment(segment, index)}
                  >
                    <div className="flex items-center gap-2">
                      <Badge 
                        variant={segment.speaker === 'host' ? 'default' : 'secondary'}
                        className="text-xs"
                      >
                        {segment.speaker.toUpperCase()}
                      </Badge>
                      <span className="text-sm">Segment {index + 1}</span>
                    </div>
                    <Download className="h-4 w-4" />
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
} 