import { createRouteHandler } from "uploadthing/next";
import { uploadRouter } from "@/lib/uploadthing";
 
export const { GET, POST } = createRouteHandler({
  router: uploadRouter,
}); 