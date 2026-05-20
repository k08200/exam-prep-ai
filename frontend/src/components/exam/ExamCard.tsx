'use client';
import { useRouter } from 'next/navigation';
import { BookOpen, Clock, CheckCircle, Zap, Trash2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { TokenCounter } from '@/components/ui/TokenCounter';
import { formatDate, getScoreColor } from '@/lib/utils';
import type { Exam } from '@/types';

interface ExamCardProps {
  exam: Exam;
  onDelete?: (exam: Exam) => void;
}

const STATUS_CONFIG = {
  draft: { label: 'Draft', className: 'bg-gray-100 text-gray-600' },
  active: { label: 'In Progress', className: 'bg-blue-100 text-blue-700' },
  completed: { label: 'Completed', className: 'bg-green-100 text-green-700' },
};

export function ExamCard({ exam, onDelete }: ExamCardProps) {
  const router = useRouter();
  const statusCfg = STATUS_CONFIG[exam.status];
  const scorePercent = exam.score !== null ? Math.round(exam.score) : null;

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              {/* Mode badge */}
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                  exam.mode === 'cram'
                    ? 'bg-amber-100 text-amber-700'
                    : 'bg-indigo-100 text-indigo-700'
                }`}
              >
                {exam.mode === 'cram' ? (
                  <Zap className="h-3 w-3" />
                ) : (
                  <BookOpen className="h-3 w-3" />
                )}
                {exam.mode === 'cram' ? 'Cram Mode' : 'Standard Mode'}
              </span>
              {/* Status badge */}
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusCfg.className}`}
              >
                {statusCfg.label}
              </span>
            </div>

            <h3 className="font-semibold text-gray-900 truncate">{exam.title}</h3>

            <div className="flex items-center gap-4 mt-1.5 text-xs text-gray-500">
              <span className="flex items-center gap-1">
                <BookOpen className="h-3 w-3" />
                {exam.question_count} questions
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDate(exam.created_at)}
              </span>
            </div>
          </div>

          {/* Score */}
          {scorePercent !== null && (
            <div className="flex-shrink-0 text-center">
              <div
                className={`text-2xl font-bold ${getScoreColor(scorePercent)}`}
              >
                {scorePercent}%
              </div>
              <div className="flex items-center gap-1 text-xs text-gray-400 mt-0.5">
                <CheckCircle className="h-3 w-3 text-green-500" />
                Score
              </div>
            </div>
          )}
        </div>

        {/* Score bar */}
        {scorePercent !== null && (
          <div className="mt-3 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                scorePercent >= 80
                  ? 'bg-green-500'
                  : scorePercent >= 60
                  ? 'bg-amber-500'
                  : 'bg-red-500'
              }`}
              style={{ width: `${scorePercent}%` }}
            />
          </div>
        )}

        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
          <TokenCounter tokens={exam.total_tokens_used} label="AI tokens" animated={false} />
          <div className="flex gap-2">
            {onDelete && (
              <button
                onClick={() => onDelete(exam)}
                className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                aria-label="Delete exam"
                title="Delete exam"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
            {exam.status === 'active' && (
              <Button
                size="sm"
                onClick={() => router.push(`/exam/${exam.id}`)}
              >
                Continue
              </Button>
            )}
            {exam.status === 'completed' && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => router.push(`/exam/${exam.id}`)}
              >
                View Results
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
