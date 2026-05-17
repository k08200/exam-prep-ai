import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'Exam Prep AI',
    template: '%s | Exam Prep AI',
  },
  description:
    'AI-powered personalized exam preparation. Upload lecture materials, analyze your professor\'s exam style, and generate unlimited mock exams.',
  keywords: ['exam prep', 'AI', 'study', 'mock exam', 'personalized learning'],
  authors: [{ name: 'Exam Prep AI' }],
  viewport: 'width=device-width, initial-scale=1',
  themeColor: '#2563eb',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-gray-50 antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
