import type { Metadata } from "next";
import { Geist } from "next/font/google";

import { Providers } from "./providers";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CMRS",
  description: "Cash Management & Reconciliation System",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${geistSans.variable} h-full antialiased`}>
      <body suppressHydrationWarning className="min-h-full bg-primary text-ink">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
