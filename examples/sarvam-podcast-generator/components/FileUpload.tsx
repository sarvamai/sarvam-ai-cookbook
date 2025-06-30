'use client';

import { useDropzone } from 'react-dropzone';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Upload, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileUploadProps {
  onFileUpload: (file: File) => void;
}

export function FileUpload({ onFileUpload }: FileUploadProps) {
  const {
    getRootProps,
    getInputProps,
    isDragActive,
    acceptedFiles,
    fileRejections,
  } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    maxSize: 2 * 1024 * 1024, // 2MB in bytes
    onDrop: (files: File[]) => {
      if (files.length > 0) {
        onFileUpload(files[0]);
      }
    },
  });

  const hasFileErrors = fileRejections.length > 0;

  return (
    <div className="space-y-4">
      <Card 
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed cursor-pointer transition-all duration-200 hover:border-primary/50",
          isDragActive 
            ? "border-primary bg-primary/5 scale-[1.02]" 
            : "border-muted-foreground/25 hover:bg-muted/20",
          hasFileErrors && "border-destructive/50"
        )}
      >
        <CardContent className="flex flex-col items-center justify-center p-8 text-center">
          <input {...getInputProps()} />
          
          <div className={cn(
            "mb-4 rounded-full p-4 transition-colors",
            isDragActive 
              ? "bg-primary/10 text-primary" 
              : hasFileErrors
              ? "bg-destructive/10 text-destructive"
              : "bg-muted text-muted-foreground"
          )}>
            <Upload className="h-8 w-8" />
          </div>

          <div className="space-y-2">
            <h3 className="text-lg font-semibold">
              {isDragActive ? 'Drop your PDF here' : 'Upload PDF Document'}
            </h3>
            <p className="text-sm text-muted-foreground">
              Drag and drop your PDF file here, or click to browse
            </p>
          </div>

          <div className="mt-4 flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              PDF only
            </Badge>
            <Badge variant="outline" className="text-xs">
              Max 2MB
            </Badge>
          </div>

          <Button 
            variant="outline" 
            className="mt-4"
            onClick={(e) => e.stopPropagation()}
          >
            <FileText className="w-4 h-4 mr-2" />
            Choose File
          </Button>
        </CardContent>
      </Card>

      {/* File Size Error */}
      {hasFileErrors && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {fileRejections[0].errors.map((error) => {
              if (error.code === 'file-too-large') {
                return `File size exceeds 2MB limit. Your file is ${(fileRejections[0].file.size / 1024 / 1024).toFixed(2)}MB.`;
              }
              if (error.code === 'file-invalid-type') {
                return 'Only PDF files are allowed.';
              }
              return error.message;
            }).join(' ')}
          </AlertDescription>
        </Alert>
      )}

      {acceptedFiles.length > 0 && (
        <Card className="border-emerald-800 bg-emerald-950/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-900/30">
                  <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-emerald-100 truncate">
                  {acceptedFiles[0].name}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="secondary" className="text-xs">
                    {(acceptedFiles[0].size / 1024 / 1024).toFixed(2)} MB
                  </Badge>
                  <span className="text-xs text-emerald-600 dark:text-emerald-400">
                    Ready to process
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
} 