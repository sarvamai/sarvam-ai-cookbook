import { NextRequest, NextResponse } from 'next/server';
import { Mistral } from '@mistralai/mistralai';

const mistral = new Mistral({
  apiKey: process.env.MISTRAL_API_KEY ?? '',
});

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('pdf') as File;
    
    if (!file) {
      return NextResponse.json({ error: 'No PDF file provided' }, { status: 400 });
    }

    if (file.type !== 'application/pdf') {
      return NextResponse.json({ error: 'Only PDF files are allowed' }, { status: 400 });
    }

    const arrayBuffer = await file.arrayBuffer();
    const base64Content = Buffer.from(arrayBuffer).toString('base64');
    const dataUri = `data:application/pdf;base64,${base64Content}`;

    const ocrResult = await mistral.ocr.process({
      model: 'mistral-ocr-latest',
      document: {
        documentUrl: dataUri,
        type: 'document_url',
      },
    });
    
    let fullText = '';
    const images: Array<{ id: string; coordinates: { x: number; y: number; width: number; height: number } }> = [];
    
    for (const page of ocrResult.pages) {
      fullText += page.markdown + '\n\n';
      
      // Extract image information
      for (const image of page.images) {
        if (image.topLeftX !== null && image.topLeftY !== null && 
            image.bottomRightX !== null && image.bottomRightY !== null) {
          images.push({
            id: image.id,
            coordinates: {
              x: image.topLeftX,
              y: image.topLeftY,
              width: image.bottomRightX - image.topLeftX,
              height: image.bottomRightY - image.topLeftY,
            },
          });
        }
      }
    }

    return NextResponse.json({
      content: fullText.trim(),
      images,
      metadata: {
        model: ocrResult.model,
        pagesProcessed: ocrResult.usageInfo.pagesProcessed,
      },
    });

  } catch (error) {
    console.error('OCR processing error:', error);
    return NextResponse.json(
      { error: 'Failed to process PDF with OCR' },
      { status: 500 }
    );
  }
} 