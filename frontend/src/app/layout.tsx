import type { Metadata, Viewport } from 'next';
import './globals.css';
import { Providers } from './providers';

export const metadata: Metadata = {
  title: {
    default: 'Exam Prep AI',
    template: '%s | Exam Prep AI',
  },
  description:
    'AI-powered personalized exam preparation. Upload lecture materials, analyze your professor\'s exam style, and generate unlimited mock exams.',
  keywords: ['exam prep', 'AI', 'study', 'mock exam', 'personalized learning'],
  authors: [{ name: 'Exam Prep AI' }],
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#2563eb',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
