'use client';
import { CheckCircle, XCircle } from 'lucide-react';
import { cn, getDifficultyColor } from '@/lib/utils';
import type { ExamQuestion } from '@/types';

interface QuestionResult {
  is_correct: boolean;
  student_answer: string;
  correct_answer: string;
  ai_feedback: string;
}

interface QuestionCardProps {
  question: ExamQuestion;
  answer: string;
  onAnswerChange: (value: string) => void;
  isSubmitted: boolean;
  result?: QuestionResult;
  totalQuestions: number;
}

const QUESTION_TYPE_LABEL: Record<ExamQuestion['question_type'], string> = {
  multiple_choice: 'Multiple Choice',
  essay: 'Essay',
  calculation: 'Calculation',
  true_false: 'True / False',
};

export function QuestionCard({
  question,
  answer,
  onAnswerChange,
  isSubmitted,
  result,
  totalQuestions,
}: QuestionCardProps) {
  const difficultyClass = getDifficultyColor(question.difficulty);

  return (
    <div
      className={cn(
        'border rounded-xl p-5 transition-all',
        isSubmitted && result
          ? result.is_correct
            ? 'border-green-200 bg-green-50/30'
            : 'border-red-200 bg-red-50/30'
          : 'border-gray-200 bg-white hover:border-blue-200'
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-bold text-gray-500">
            Q{question.question_number}
            <span className="font-normal text-gray-400"> / {totalQuestions}</span>
          </span>
          <span
            className={cn(
              'px-2 py-0.5 rounded-full text-xs font-medium capitalize',
              difficultyClass
            )}
          >
            {question.difficulty}
          </span>
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700">
            {QUESTION_TYPE_LABEL[question.question_type]}
          </span>
        </div>
        {isSubmitted && result && (
          <div className="flex-shrink-0">
            {result.is_correct ? (
              <CheckCircle className="h-5 w-5 text-green-500" />
            ) : (
              <XCircle className="h-5 w-5 text-red-500" />
            )}
          </div>
        )}
      </div>

      {/* Question text */}
      <p className="text-gray-900 font-medium leading-relaxed mb-4">
        {question.question_text}
      </p>

      {/* Answer input */}
      {!isSubmitted ? (
        <div className="space-y-2">
          {question.question_type === 'multiple_choice' && question.choices && (
            <div className="space-y-2">
              {question.choices.map((choice) => (
                <label
                  key={choice.label}
                  className={cn(
                    'flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all',
                    answer === choice.label
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                  )}
                >
                  <input
                    type="radio"
                    name={`question-${question.id}`}
                    value={choice.label}
                    checked={answer === choice.label}
                    onChange={() => onAnswerChange(choice.label)}
                    className="text-blue-600 focus:ring-blue-500"
                  />
                  <span className="font-semibold text-gray-600 w-5 flex-shrink-0">
                    {choice.label}.
                  </span>
                  <span className="text-gray-800 text-sm">{choice.text}</span>
                </label>
              ))}
            </div>
          )}

          {question.question_type === 'true_false' && (
            <div className="flex gap-3">
              {['True', 'False'].map((opt) => (
                <label
                  key={opt}
                  className={cn(
                    'flex-1 flex items-center justify-center gap-2 p-3 rounded-lg border cursor-pointer transition-all font-medium',
                    answer === opt
                      ? opt === 'True'
                        ? 'border-green-500 bg-green-50 text-green-700'
                        : 'border-red-500 bg-red-50 text-red-700'
                      : 'border-gray-200 hover:border-gray-300 text-gray-700'
                  )}
                >
                  <input
                    type="radio"
                    name={`question-${question.id}`}
                    value={opt}
                    checked={answer === opt}
                    onChange={() => onAnswerChange(opt)}
                    className="sr-only"
                  />
                  <span>{opt === 'True' ? '✓' : '✗'}</span>
                  <span>{opt}</span>
                </label>
              ))}
            </div>
          )}

          {question.question_type === 'essay' && (
            <textarea
              value={answer}
              onChange={(e) => onAnswerChange(e.target.value)}
              placeholder="Write your answer here..."
              rows={5}
              className="w-full px-3 py-2.5 text-sm text-gray-900 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y min-h-[100px]"
            />
          )}

          {question.question_type === 'calculation' && (
            <div className="relative">
              <input
                type="text"
                value={answer}
                onChange={(e) => onAnswerChange(e.target.value)}
                placeholder="Enter your numerical answer..."
                className="w-full px-3 py-2.5 text-sm text-gray-900 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono"
              />
            </div>
          )}
        </div>
      ) : (
        /* After submission: show results */
        <div className="space-y-3">
          {/* Student answer */}
          <div
            className={cn(
              'p-3 rounded-lg border',
              result?.is_correct
                ? 'bg-green-50 border-green-200'
                : 'bg-red-50 border-red-200'
            )}
          >
            <div className="flex items-center gap-1.5 mb-1">
              {result?.is_correct ? (
                <CheckCircle className="h-3.5 w-3.5 text-green-600" />
              ) : (
                <XCircle className="h-3.5 w-3.5 text-red-600" />
              )}
              <span
                className={cn(
                  'text-xs font-semibold',
                  result?.is_correct ? 'text-green-700' : 'text-red-700'
                )}
              >
                Your Answer
              </span>
            </div>
            <p className="text-sm text-gray-800">{result?.student_answer || answer || '(no answer)'}</p>
          </div>

          {/* Correct answer (only if wrong) */}
          {result && !result.is_correct && (
            <div className="p-3 rounded-lg bg-green-50 border border-green-200">
              <p className="text-xs font-semibold text-green-700 mb-1">Correct Answer</p>
              <p className="text-sm text-gray-800">{result.correct_answer}</p>
            </div>
          )}

          {/* AI feedback */}
          {result?.ai_feedback && (
            <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
              <p className="text-xs font-semibold text-blue-700 mb-1">AI Feedback</p>
              <p className="text-sm text-gray-700 leading-relaxed">{result.ai_feedback}</p>
            </div>
          )}

          {/* Concepts */}
          {question.concepts.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {question.concepts.map((concept) => (
                <span
                  key={concept}
                  className="px-2 py-0.5 bg-violet-50 text-violet-700 text-xs rounded-full border border-violet-200"
                >
                  {concept}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
