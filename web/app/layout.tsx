import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "highlight.js/styles/github-dark.css";
import "./globals.css";
import { themeBootScript } from "@/components/ThemeToggle";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Auralynq — Talk to Your Data",
  description:
    "Local-first, agentic, voice-enabled RAG with PathRAG graph retrieval. Grounded, cited answers — at $0 by default.",
  openGraph: {
    title: "Auralynq — Talk to Your Data",
    description:
      "Local-first, agentic, voice-enabled RAG with PathRAG graph retrieval. Grounded, cited answers.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
