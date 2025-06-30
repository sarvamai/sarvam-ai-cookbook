import { inngest } from '../lib/inngest';
import { utapi } from '../lib/uploadthing';

export const audioCleanupFunction = inngest.createFunction(
  {
    id: 'audio-cleanup',
    name: 'Audio Data URL Cleanup'
  },
  { event: 'audio/cleanup' },
  async ({ event, step }) => {
    const { fileKeys, jobId, type, delayMinutes } = event.data;

    try {
      console.log(`Starting ${type} cleanup for job ${jobId}`);

      if (type === 'single-job') {
        // Cleanup data URL files for a specific job
        await step.run('delete-job-files', async () => {
          if (!fileKeys || fileKeys.length === 0) {
            console.log(`No data URL files to cleanup for job: ${jobId}`);
            return { deleted: 0 };
          }

          console.log(`Deleting ${fileKeys.length} data URL files for job: ${jobId}`);
          await utapi.deleteFiles(fileKeys);
          console.log(`Successfully deleted data URL files for job: ${jobId}`);
          
          return { deleted: fileKeys.length };
        });
      } else if (type === 'scheduled-cleanup') {
        // Wait for the specified delay before cleanup
        if (delayMinutes) {
          await step.sleep('cleanup-delay', `${delayMinutes}m`);
        }
        
        // Scheduled cleanup for data URL files after delay
        await step.run('delete-scheduled-file', async () => {
          if (!fileKeys || fileKeys.length === 0) {
            console.log(`No data URL files provided for scheduled cleanup`);
            return { deleted: 0 };
          }

          console.log(`Scheduled cleanup: deleting ${fileKeys.length} data URL files`);
          await utapi.deleteFiles(fileKeys);
          console.log(`Scheduled cleanup completed: deleted ${fileKeys.length} data URL files`);
          
          return { deleted: fileKeys.length };
        });
      }

      return { success: true, type, jobId, filesDeleted: fileKeys?.length || 0 };
    } catch (error) {
      console.error(`Error in ${type} cleanup for job ${jobId}:`, error);
      throw error;
    }
  }
); 