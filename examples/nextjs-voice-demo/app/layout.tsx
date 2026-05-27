import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sarvam AI Voice Demo",
  description:
    "Interactive Next.js demo for Sarvam AI's multilingual voice APIs — " +
    "Text-to-Speech (Bulbul), Speech-to-Text (Saarika), and Transliteration " +
    "across 10 Indian languages.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
