import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ApexMind AI",
  description: "Model-agnostic AI agent command center",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
