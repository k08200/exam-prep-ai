'use client';
import { useState, useMemo, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  CheckCircle,
  AlertTriangle,
  BookOpen,
  Send,
  Trophy,
  Brain,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { QuestionCard } from '@/components/exam/QuestionCard';
import { ExamResults } from '@/components/exam/ExamResults';
import { examsApi } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import type { Exam, ExamResult } from '@/types';

export default function ExamPage() {
  const params = useParams();
  const examId = params.examId as string;
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, loading: authLoading } = useAuth();

  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [examResult, setExamResult] = useState<ExamResult | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [isGrading, setIsGrading] = useState(false);
  const [gradingText, setGradingText] = useState('');

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/auth/login');
    }
  }, [authLoading, user, router]);

  // Fetch exam with questions
  const { data: exam, isLoading: examLoading } = useQuery<Exam>({
    queryKey: ['exam', examId],
    queryFn: async () => {
      const res = await examsApi.get(examId);
      return res.data;
    },
    enabled: !!user,
  });

  const {
    data: persistedResult,
    isLoading: resultLoading,
    error: resultError,
  } = useQuery<ExamResult>({
    queryKey: ['examResult', examId],
    queryFn: async () => {
      const res = await examsApi.result(examId);
      return res.data;
    },
    enabled: !!user && exam?.status === 'completed',
    retry: false,
  });

  const questions = exam?.questions ?? [];

  const answeredCount = useMemo(() => {
    return questions.filter(
      (q) => answers[q.id] !== undefined && answers[q.id].trim() !== ''
    ).length;
  }, [questions, answers]);

  const allAnswered = answeredCount === questions.length && questions.length > 0;

  const handleAnswerChange = (questionId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleSubmit = async () => {
    setShowConfirmDialog(false);
    setIsSubmitting(true);
    setSubmitError(null);
    setIsGrading(true);
    setGradingText('');

    try {
      const submissionAnswers = questions.map((q) => ({
        question_id: q.id,
        student_answer: answers[q.id] || '',
      }));

      setGradingText('Submitting answers...');
      const res = await examsApi.submit(examId, submissionAnswers);
      setExamResult(res.data);
      queryClient.invalidateQueries({ queryKey: ['exam', examId] });
      if (exam?.course_id) {
        queryClient.invalidateQueries({ queryKey: ['exams', exam?.course_id] });
        queryClient.invalidateQueries({ queryKey: ['recentExams'] });
      }
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      const msg = err instanceof Error ? err.message : 'Submission failed. Please try again.';
      setSubmitError(detail || msg);
    } finally {
      setIsSubmitting(false);
      setIsGrading(false);
    }
  };

  if (authLoading || examLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-500">Loading exam…</p>
        </div>
      </div>
    );
  }

  if (!exam) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-gray-600">Exam not found.</p>
        <Button onClick={() => router.push('/dashboard')}>
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Button>
      </div>
    );
  }

  // Grading animation screen
  if (isGrading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-gradient-to-br from-blue-50 to-violet-50">
        <div className="max-w-md w-full text-center space-y-6">
          <div className="relative w-24 h-24 mx-auto">
            <div className="absolute inset-0 rounded-full gradient-hero opacity-10 animate-ping" />
            <div className="relative w-24 h-24 gradient-hero rounded-full flex items-center justify-center">
              <Brain className="h-10 w-10 text-white" />
            </div>
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">Grading Your Exam</h2>
            <p className="text-gray-500 text-sm mt-1">
              AI is reviewing your answers and generating personalized feedback…
            </p>
          </div>
          {gradingText && (
            <div className="text-left bg-white/80 rounded-xl p-4 border border-gray-100 max-h-48 overflow-y-auto">
              <p className="text-xs font-mono text-gray-600 leading-relaxed">{gradingText}</p>
            </div>
          )}
          <div className="flex justify-center">
            <div className="flex gap-2">
              {[0, 1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="w-2 h-2 rounded-full bg-blue-400 animate-bounce"
                  style={{ animationDelay: `${i * 100}ms` }}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Results screen
  if (examResult) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center justify-between mb-6">
            <button
              onClick={() =>
                router.push(exam.course_id ? `/courses/${exam.course_id}` : '/dashboard')
              }
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Course
            </button>
            <div className="flex items-center gap-2">
              <Trophy className="h-5 w-5 text-yellow-500" />
              <span className="font-semibold text-gray-900">Exam Results</span>
            </div>
          </div>

          <Card>
            <CardContent>
              <ExamResults result={examResult} questions={questions} />
            </CardContent>
          </Card>

          <div className="flex justify-center mt-6">
            <Button
              onClick={() =>
                router.push(exam.course_id ? `/courses/${exam.course_id}` : '/dashboard')
              }
            >
              <BookOpen className="h-4 w-4" />
              Back to Course
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // If exam is already completed
  if (exam.status === 'completed') {
    if (resultLoading) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="h-10 w-10 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-gray-500">Loading results...</p>
          </div>
        </div>
      );
    }

    if (persistedResult) {
      return (
        <div className="min-h-screen bg-gray-50">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="flex items-center justify-between mb-6">
              <button
                onClick={() =>
                  router.push(exam.course_id ? `/courses/${exam.course_id}` : '/dashboard')
                }
                className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to Course
              </button>
              <div className="flex items-center gap-2">
                <Trophy className="h-5 w-5 text-yellow-500" />
                <span className="font-semibold text-gray-900">Exam Results</span>
              </div>
            </div>

            <Card>
              <CardContent>
                <ExamResults result={persistedResult} questions={questions} />
              </CardContent>
            </Card>
          </div>
        </div>
      );
    }

    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-6">
        <CheckCircle className="h-12 w-12 text-green-500" />
        <div className="text-center">
          <h2 className="text-xl font-bold text-gray-900">Exam Completed</h2>
          <p className="text-gray-500 text-sm mt-1">
            This exam has already been submitted.
          </p>
          {exam.score !== null && (
            <p className="text-3xl font-black text-blue-600 mt-3">
              {Math.round(exam.score)}%
            </p>
          )}
          {resultError && (
            <p className="text-sm text-red-600 mt-3">
              Could not load detailed feedback. Please try again later.
            </p>
          )}
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => router.push('/dashboard')}>
            Dashboard
          </Button>
          <Button
            onClick={() =>
              router.push(exam.course_id ? `/courses/${exam.course_id}` : '/dashboard')
            }
          >
            Back to Course
          </Button>
        </div>
      </div>
    );
  }

  // Exam taking view
  return (
    <div className="min-h-screen bg-gray-50 pb-32">
      {/* Header */}
      <div className="sticky top-0 z-30 bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
          <button
            onClick={() => router.push(exam.course_id ? `/courses/${exam.course_id}` : '/dashboard')}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden sm:inline">Back to Course</span>
          </button>

          <div className="flex-1 text-center">
            <h1 className="font-semibold text-gray-900 text-sm truncate">{exam.title}</h1>
          </div>

          <div className="text-sm text-gray-500 flex-shrink-0">
            <span className="font-semibold text-gray-900">{answeredCount}</span>
            /{questions.length} answered
          </div>
        </div>

        {/* Progress bar */}
        <div className="h-0.5 bg-gray-100">
          <div
            className="h-full bg-blue-500 transition-all duration-300"
            style={{
              width: questions.length > 0 ? `${(answeredCount / questions.length) * 100}%` : '0%',
            }}
          />
        </div>
      </div>

      {/* Questions */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-4">
        {questions.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-500">No questions available for this exam.</p>
          </div>
        ) : (
          questions.map((question) => (
            <QuestionCard
              key={question.id}
              question={question}
              answer={answers[question.id] || ''}
              onAnswerChange={(value) => handleAnswerChange(question.id, value)}
              isSubmitted={false}
              totalQuestions={questions.length}
            />
          ))
        )}
      </div>

      {/* Sticky submit bar */}
      <div className="fixed bottom-0 inset-x-0 z-30 bg-white border-t border-gray-200 shadow-lg">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="text-sm">
              <span className="font-semibold text-gray-900">{answeredCount}</span>
              <span className="text-gray-500"> of {questions.length} answered</span>
            </div>
            {!allAnswered && answeredCount > 0 && (
              <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
                {questions.length - answeredCount} unanswered
              </span>
            )}
          </div>

          {submitError && (
            <div className="flex items-center gap-1.5 text-xs text-red-600 flex-1">
              <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="truncate">{submitError}</span>
            </div>
          )}

          <Button
            onClick={() => setShowConfirmDialog(true)}
            loading={isSubmitting}
            disabled={questions.length === 0}
            size="md"
          >
            <Send className="h-4 w-4" />
            Submit Exam
          </Button>
        </div>
      </div>

      {/* Confirm Submit Modal */}
      <Modal
        isOpen={showConfirmDialog}
        onClose={() => setShowConfirmDialog(false)}
        title="Submit Exam?"
        description="Make sure you've reviewed all your answers before submitting."
        size="sm"
      >
        {!allAnswered && (
          <div className="flex items-start gap-2.5 p-3 bg-amber-50 border border-amber-200 rounded-lg mb-4 text-sm text-amber-800">
            <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5 text-amber-600" />
            <div>
              <p className="font-medium">
                {questions.length - answeredCount} question
                {questions.length - answeredCount !== 1 ? 's' : ''} unanswered
              </p>
              <p className="text-xs text-amber-600 mt-0.5">
                Unanswered questions will be marked incorrect.
              </p>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg mb-4 text-sm">
          <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
          <div>
            <p className="font-medium text-gray-800">
              {answeredCount} of {questions.length} answered
            </p>
            <p className="text-xs text-gray-500 mt-0.5">
              Your exam will be graded by AI immediately after submission.
            </p>
          </div>
        </div>

        <div className="flex gap-3">
          <Button
            variant="secondary"
            className="flex-1"
            onClick={() => setShowConfirmDialog(false)}
          >
            Review Answers
          </Button>
          <Button
            className="flex-1"
            onClick={handleSubmit}
            loading={isSubmitting}
          >
            Submit Now
          </Button>
        </div>
      </Modal>
    </div>
  );
}
