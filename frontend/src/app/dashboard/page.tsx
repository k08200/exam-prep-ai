'use client';
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import Link from 'next/link';
import {
  Plus,
  BookOpen,
  Brain,
  ChevronRight,
  Trash2,
  AlertCircle,
  BarChart3,
  Trophy,
  Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { coursesApi, examsApi } from '@/lib/api';
import { formatDate, getScoreColor } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import type { Course, Exam } from '@/types';

const courseSchema = z.object({
  name: z.string().min(1, 'Course name is required').max(100),
  professor_name: z.string().optional(),
  subject: z.string().optional(),
  description: z.string().optional(),
});

type CourseFormData = z.infer<typeof courseSchema>;

function CourseCard({ course, onDelete }: { course: Course; onDelete: (id: string) => void }) {
  return (
    <Card className="hover:shadow-md transition-all group">
      <CardContent className="py-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              {course.has_analysis && (
                <span className="px-1.5 py-0.5 bg-violet-100 text-violet-700 text-xs rounded font-medium">
                  Analyzed
                </span>
              )}
              {course.subject && (
                <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
                  {course.subject}
                </span>
              )}
            </div>
            <h3 className="font-semibold text-gray-900 truncate">{course.name}</h3>
            {course.professor_name && (
              <p className="text-sm text-gray-500 mt-0.5">
                Prof. {course.professor_name}
              </p>
            )}
            {course.description && (
              <p className="text-xs text-gray-400 mt-1 line-clamp-2">{course.description}</p>
            )}

            <div className="flex items-center gap-4 mt-3 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <BookOpen className="h-3 w-3" />
                {course.material_count} material{course.material_count !== 1 ? 's' : ''}
              </span>
              <span>{formatDate(course.created_at)}</span>
            </div>
          </div>

          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(course.id);
            }}
            className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
            aria-label="Delete course"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100">
          <div className="flex gap-1.5">
            {course.has_analysis ? (
              <span className="flex items-center gap-1 text-xs text-violet-600">
                <Brain className="h-3 w-3" />
                AI Analysis ready
              </span>
            ) : (
              <span className="text-xs text-gray-400">No analysis yet</span>
            )}
          </div>
          <Link href={`/courses/${course.id}`}>
            <Button size="sm" variant="outline">
              Open
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const { data: courses = [], isLoading } = useQuery<Course[]>({
    queryKey: ['courses'],
    queryFn: async () => {
      const res = await coursesApi.list();
      return res.data;
    },
  });

  const { data: recentExams = [] } = useQuery<Exam[]>({
    queryKey: ['recentExams'],
    queryFn: async () => {
      const res = await examsApi.listAll(5);
      return res.data;
    },
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CourseFormData>({
    resolver: zodResolver(courseSchema),
  });

  const handleCreate = async (data: CourseFormData) => {
    setCreateError(null);
    try {
      await coursesApi.create({
        name: data.name,
        professor_name: data.professor_name || undefined,
        subject: data.subject || undefined,
        description: data.description || undefined,
      });
      queryClient.invalidateQueries({ queryKey: ['courses'] });
      setIsCreateOpen(false);
      reset();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setCreateError(axiosErr.response?.data?.detail || 'Failed to create course.');
      } else {
        setCreateError('Failed to create course. Please try again.');
      }
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this course and all its materials and exams?')) return;
    try {
      await coursesApi.delete(id);
      queryClient.invalidateQueries({ queryKey: ['courses'] });
    } catch {
      // deletion failure handled silently
    }
  };

  const firstName = user?.full_name?.split(' ')[0] || 'Student';

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back, {firstName}!
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            {courses.length} course{courses.length !== 1 ? 's' : ''} ready to study
          </p>
        </div>
        <Button onClick={() => setIsCreateOpen(true)}>
          <Plus className="h-4 w-4" />
          New Course
        </Button>
      </div>

      {/* Stats row */}
      {courses.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {[
            {
              label: 'Courses',
              value: courses.length,
              icon: <BookOpen className="h-5 w-5 text-blue-600" />,
              bg: 'bg-blue-50',
            },
            {
              label: 'Analyzed',
              value: courses.filter((c) => c.has_analysis).length,
              icon: <Brain className="h-5 w-5 text-violet-600" />,
              bg: 'bg-violet-50',
            },
            {
              label: 'Materials',
              value: courses.reduce((sum, c) => sum + c.material_count, 0),
              icon: <BookOpen className="h-5 w-5 text-indigo-600" />,
              bg: 'bg-indigo-50',
            },
            {
              label: 'Ready to Exam',
              value: courses.filter((c) => c.has_analysis && c.material_count > 0).length,
              icon: <BarChart3 className="h-5 w-5 text-green-600" />,
              bg: 'bg-green-50',
            },
          ].map((stat) => (
            <div
              key={stat.label}
              className={`${stat.bg} rounded-xl p-4 flex items-center gap-3`}
            >
              <div className="bg-white p-2 rounded-lg shadow-sm">{stat.icon}</div>
              <div>
                <div className="text-xl font-bold text-gray-900">{stat.value}</div>
                <div className="text-xs text-gray-500">{stat.label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Recent Exams */}
      {recentExams.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Recent Practice</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {recentExams.slice(0, 3).map((exam) => {
              const score = exam.score !== null ? Math.round(exam.score) : null;
              return (
                <Link key={exam.id} href={`/exam/${exam.id}`}>
                  <div className="flex items-center gap-3 p-3 bg-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow cursor-pointer">
                    <div className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${exam.mode === 'cram' ? 'bg-amber-50' : 'bg-indigo-50'}`}>
                      {exam.mode === 'cram' ? (
                        <Zap className="h-5 w-5 text-amber-500" />
                      ) : (
                        <BookOpen className="h-5 w-5 text-indigo-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{exam.title}</p>
                      <p className="text-xs text-gray-400 mt-0.5">{formatDate(exam.created_at)}</p>
                    </div>
                    {score !== null && (
                      <div className={`flex-shrink-0 text-sm font-bold ${getScoreColor(score)}`}>
                        {score}%
                      </div>
                    )}
                    {score === null && (
                      <span className="text-xs text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded font-medium">Active</span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Courses grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-44 bg-white rounded-xl border border-gray-200 animate-pulse" />
          ))}
        </div>
      ) : courses.length === 0 ? (
        <div className="text-center py-20">
          <div className="flex justify-center mb-4">
            <div className="w-16 h-16 gradient-hero rounded-2xl flex items-center justify-center opacity-20">
              <Brain className="h-8 w-8 text-white" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Create Your First Course
          </h3>
          <p className="text-gray-500 text-sm max-w-sm mx-auto mb-6">
            Add a course to start uploading materials and generating AI-personalized
            mock exams.
          </p>
          <Button onClick={() => setIsCreateOpen(true)} size="lg">
            <Plus className="h-5 w-5" />
            Create Course
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {courses.map((course) => (
            <CourseCard key={course.id} course={course} onDelete={handleDelete} />
          ))}
          {/* Add more card */}
          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex flex-col items-center justify-center p-8 border-2 border-dashed border-gray-200 rounded-xl text-gray-400 hover:border-blue-400 hover:text-blue-500 hover:bg-blue-50 transition-all"
          >
            <Plus className="h-8 w-8 mb-2" />
            <span className="text-sm font-medium">Add Course</span>
          </button>
        </div>
      )}

      {/* Create Course Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => {
          setIsCreateOpen(false);
          setCreateError(null);
          reset();
        }}
        title="Create New Course"
        description="Add your course details to get started with AI-powered exam prep."
      >
        {createError && (
          <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg mb-4 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>{createError}</span>
          </div>
        )}
        <form onSubmit={handleSubmit(handleCreate)} className="space-y-4">
          <div>
            <label className="label-base">
              Course Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              className={`input-base ${errors.name ? 'border-red-400' : ''}`}
              placeholder="e.g., Introduction to Machine Learning"
              {...register('name')}
            />
            {errors.name && (
              <p className="error-message">
                <AlertCircle className="h-3 w-3" />
                {errors.name.message}
              </p>
            )}
          </div>

          <div>
            <label className="label-base">Professor Name</label>
            <input
              type="text"
              className="input-base"
              placeholder="e.g., Dr. Smith"
              {...register('professor_name')}
            />
          </div>

          <div>
            <label className="label-base">Subject</label>
            <input
              type="text"
              className="input-base"
              placeholder="e.g., Computer Science, Biology"
              {...register('subject')}
            />
          </div>

          <div>
            <label className="label-base">Description</label>
            <textarea
              className="input-base resize-none"
              rows={3}
              placeholder="Brief description of the course..."
              {...register('description')}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setIsCreateOpen(false);
                reset();
              }}
            >
              Cancel
            </Button>
            <Button type="submit" loading={isSubmitting}>
              Create Course
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
