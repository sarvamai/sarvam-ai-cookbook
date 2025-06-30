import { NextRequest, NextResponse } from 'next/server';
import { getAllAudioFileRecords } from '@/lib/cleanup-audio-files';

export async function GET() {
  try {
    const records = getAllAudioFileRecords();
    
    return NextResponse.json({
      success: true,
      data: {
        totalJobs: records.length,
        totalFiles: records.reduce((sum, record) => sum + record.fileKeys.length, 0),
        records: records.map(record => ({
          jobId: record.jobId,
          fileCount: record.fileKeys.length,
          uploadedAt: record.uploadedAt,
          ageInHours: Math.round((Date.now() - record.uploadedAt.getTime()) / (1000 * 60 * 60))
        }))
      }
    });
  } catch (error) {
    console.error('Error getting audio file records:', error);
    return NextResponse.json(
      { 
        success: false, 
        error: `Failed to get records: ${error instanceof Error ? error.message : 'Unknown error'}` 
      },
      { status: 500 }
    );
  }
} 