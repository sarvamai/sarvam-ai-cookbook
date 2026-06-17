import { createUploadthing, type FileRouter } from 'uploadthing/next';

const f = createUploadthing();

export const uploadRouter = {
  pdfUploader: f({ pdf: { maxFileSize: '16MB' } })
    .middleware(async () => ({}))
    .onUploadComplete(async () => {}),
} satisfies FileRouter;

export type OurFileRouter = typeof uploadRouter;

// Stub for local dev — no UPLOADTHING_TOKEN required
export const utapi = {
  deleteFiles: async (fileKeys: string[]) => {
    console.log(`[local] Skipping deletion of ${fileKeys.length} file(s):`, fileKeys);
    return { deletedCount: fileKeys.length };
  },
};
