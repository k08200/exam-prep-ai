'use client';
import { CheckCircle, XCircle, Trophy } from 'lucide-react';
import { TokenCounter } from '@/components/ui/TokenCounter';
import { cn, getScoreColor, getScoreBgColor } from '@/lib/utils';
import type { ExamResult, ExamQuestion } from '@/types';

interface ExamResultsProps {
  result: ExamResult;
  questions: ExamQuestion[];
}

function ScoreMeter({ score }: { score: number }) {
  const color = getScoreBgColor(score);
  return (
    <div className="relative w-36 h-36 mx-auto">
      <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
        <circle
          cx="50"
          cy="50"
          r="42"
          fill="none"
          stroke="#f3f4f6"
          strokeWidth="10"
        />
        <circle
          cx="50"
          cy="50"
          r="42"
          fill="none"
          stroke={score >= 80 ? '#22c55e' : score >= 60 ? '#f59e0b' : '#ef4444'}
          strokeWidth="10"
          strokeDasharray={`${2 * Math.PI * 42}`}
          strokeDashoffset={`${2 * Math.PI * 42 * (1 - score / 100)}`}
          strokeLinecap="round"
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn('text-3xl font-bold', getScoreColor(score))}>{Math.round(score)}%</span>
        <span className="text-xs text-gray-500 mt-0.5">Score</span>
      </div>
    </div>
  );
}

export function ExamResults({ result, questions }: ExamResultsProps) {
  const scorePercent = Math.round(result.score);

  // Map question ID to question data
  const questionMap = new Map(questions.map((q) => [q.id, q]));

  // Group concepts across all results
  const allConcepts = new Set<string>();
  result.results.forEach((r) => {
    const q = questionMap.get(r.question_id);
    if (q) q.concepts.forEach((c) => allConcepts.add(c));
  });

  const performanceLabel =
    scorePercent >= 80 ? 'Excellent!' : scorePercent >= 60 ? 'Good job!' : 'Keep practicing!';

  return (
    <div className="space-y-8">
      {/* Score Summary */}
      <div className="text-center space-y-4">
        <div className="flex items-center justify-center gap-2">
          <Trophy
            className={cn(
              'h-6 w-6',
              scorePercent >= 80
                ? 'text-yellow-500'
                : scorePercent >= 60
                ? 'text-blue-500'
                : 'text-gray-400'
            )}
          />
          <h2 className="text-xl font-bold text-gray-900">{performanceLabel}</h2>
        </div>

        <ScoreMeter score={scorePercent} />

        <div className="flex items-center justify-center gap-6 text-sm">
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">{result.correct_count}</div>
            <div className="text-gray-500 text-xs">Correct</div>
          </div>
          <div className="w-px h-10 bg-gray-200" />
          <div className="text-center">
            <div className="text-2xl font-bold text-red-500">
              {result.total_questions - result.correct_count}
            </div>
            <div className="text-gray-500 text-xs">Incorrect</div>
          </div>
          <div className="w-px h-10 bg-gray-200" />
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-700">{result.total_questions}</div>
            <div className="text-gray-500 text-xs">Total</div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="max-w-sm mx-auto">
          <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={cn('h-full rounded-full transition-all duration-1000', getScoreBgColor(scorePercent))}
              style={{ width: `${scorePercent}%` }}
            />
          </div>
        </div>

        <div className="flex justify-center">
          <TokenCounter tokens={result.total_tokens_used} label="AI grading tokens" animated={false} />
        </div>
      </div>

      {/* Concepts tested */}
      {allConcepts.size > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Concepts Tested</h3>
          <div className="flex flex-wrap gap-1.5">
            {[...allConcepts].map((concept) => (
              <span
                key={concept}
                className="px-2.5 py-1 bg-violet-50 text-violet-700 text-xs rounded-full border border-violet-200"
              >
                {concept}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Question-by-question breakdown */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">
          Question Breakdown
        </h3>
        <div className="space-y-3">
          {result.results
            .sort((a, b) => a.question_number - b.question_number)
            .map((r) => {
              const question = questionMap.get(r.question_id);
              return (
                <div
                  key={r.question_id}
                  className={cn(
                    'p-4 rounded-xl border',
                    r.is_correct
                      ? 'border-green-200 bg-green-50/40'
                      : 'border-red-200 bg-red-50/40'
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      {r.is_correct ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : (
                        <XCircle className="h-5 w-5 text-red-500" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-gray-500">
                          Q{r.question_number}
                        </span>
                        {question && (
                          <>
                            <span
                              className={cn(
                                'px-1.5 py-0.5 rounded text-xs font-medium capitalize',
                                question.difficulty === 'easy'
                                  ? 'bg-green-100 text-green-700'
                                  : question.difficulty === 'medium'
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-red-100 text-red-700'
                              )}
                            >
                              {question.difficulty}
                            </span>
                          </>
                        )}
                        <span
                          className={cn(
                            'text-xs font-semibold',
                            r.is_correct ? 'text-green-700' : 'text-red-700'
                          )}
                        >
                          {r.is_correct ? 'Correct' : 'Incorrect'}
                        </span>
                      </div>

                      {question && (
                        <p className="text-sm text-gray-700 mb-2 leading-relaxed">
                          {question.question_text}
                        </p>
                      )}

                      <div className="space-y-1.5 text-xs">
                        <div className="flex gap-2">
                          <span className="text-gray-500 w-24 flex-shrink-0">Your answer:</span>
                          <span
                            className={cn(
                              'font-medium',
                              r.is_correct ? 'text-green-700' : 'text-red-700'
                            )}
                          >
                            {r.student_answer || '(no answer)'}
                          </span>
                        </div>
                        {!r.is_correct && (
                          <div className="flex gap-2">
                            <span className="text-gray-500 w-24 flex-shrink-0">
                              Correct answer:
                            </span>
                            <span className="font-medium text-green-700">
                              {r.correct_answer}
                            </span>
                          </div>
                        )}
                      </div>

                      {r.ai_feedback && (
                        <div className="mt-2 p-2 bg-white/70 rounded-lg border border-blue-100">
                          <p className="text-xs font-semibold text-blue-700 mb-0.5">
                            AI Feedback
                          </p>
                          <p className="text-xs text-gray-600 leading-relaxed">{r.ai_feedback}</p>
                        </div>
                      )}

                      {question && question.concepts.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {question.concepts.map((c) => (
                            <span
                              key={c}
                              className="px-1.5 py-0.5 bg-violet-50 text-violet-600 text-xs rounded-full"
                            >
                              {c}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}
