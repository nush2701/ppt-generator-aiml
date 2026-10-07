import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI PowerPoint Generator",
  description: "Generate PowerPoint presentations from natural-language prompts.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
