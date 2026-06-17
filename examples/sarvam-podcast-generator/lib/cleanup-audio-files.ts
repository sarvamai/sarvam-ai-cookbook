export interface AudioFileRecord {
  jobId: string;
  fileKeys: string[];
  uploadedAt: Date;
}

const audioFileRecords: AudioFileRecord[] = [];

export function getAllAudioFileRecords(): AudioFileRecord[] {
  return audioFileRecords;
}

export function addAudioFileRecord(jobId: string, fileKeys: string[]): void {
  audioFileRecords.push({ jobId, fileKeys, uploadedAt: new Date() });
}
