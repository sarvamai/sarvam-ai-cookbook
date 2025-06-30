import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sarvam AI Podcast Generator",
  description: "AI-powered document analysis using Mistral OCR and podcast generation using Sarvam AI APIs",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 antialiased">
        {children}
      </body>
    </html>
  );
}
