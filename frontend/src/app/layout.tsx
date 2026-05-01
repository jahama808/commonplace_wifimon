import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import { QueryProvider } from '@/components/QueryProvider';
import { PRE_PAINT_SCRIPT } from '@/lib/use-theme';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});
const mono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Atrium · Common Area Monitor',
  description: 'WiFi network operations dashboard for Hawaiian-island properties',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" className={`${inter.variable} ${mono.variable}`}>
      <head>
        {/* Pre-paint theme resolver — sets `data-theme` before React hydrates
         * so the page never flashes the wrong palette. Content is a hardcoded
         * literal from `lib/use-theme.ts`, not user-supplied. */}
        <script dangerouslySetInnerHTML={{ __html: PRE_PAINT_SCRIPT }} />
      </head>
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
