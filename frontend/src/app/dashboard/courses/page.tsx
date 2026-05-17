'use client';
import { redirect } from 'next/navigation';

// Redirect /dashboard/courses to /dashboard since course management is on the main dashboard
export default function CoursesPage() {
  redirect('/dashboard');
}
