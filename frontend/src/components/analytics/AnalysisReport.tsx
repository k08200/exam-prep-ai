'use client';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import type { Analysis } from '@/types';

interface AnalysisReportProps {
  analysis: Analysis;
}

const PIE_COLORS = ['#3b82f6', '#8b5cf6', '#f59e0b', '#22c55e', '#ef4444', '#06b6d4'];

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; payload: { name: string; value: number } }>;
}

function BarTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 shadow-lg rounded-lg p-2 text-xs">
      <p className="font-medium text-gray-800">{payload[0].payload.name}</p>
      <p className="text-blue-600">Score: {payload[0].value.toFixed(2)}</p>
    </div>
  );
}

function PieTooltipContent({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 shadow-lg rounded-lg p-2 text-xs">
      <p className="font-medium text-gray-800">{payload[0].name}</p>
      <p className="text-gray-600">{payload[0].value}%</p>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-sm font-semibold text-gray-800 uppercase tracking-wider mb-3 flex items-center gap-2">
      <span className="w-1 h-4 bg-blue-600 rounded-full inline-block" />
      {children}
    </h3>
  );
}

export function AnalysisReport({ analysis }: AnalysisReportProps) {
  // Top concepts bar chart data
  const conceptData = analysis.top_concepts
    .slice(0, 10)
    .map((c) => ({
      name: c.concept.length > 20 ? `${c.concept.slice(0, 20)}…` : c.concept,
      fullName: c.concept,
      score: c.importance_score,
      frequency: c.frequency,
    }))
    .sort((a, b) => b.score - a.score);

  // Question types pie data
  const qtTotal =
    analysis.question_types.multiple_choice +
    analysis.question_types.essay +
    analysis.question_types.calculation +
    analysis.question_types.true_false;

  const questionTypeData = [
    {
      name: 'Multiple Choice',
      value:
        qtTotal > 0
          ? Math.round((analysis.question_types.multiple_choice / qtTotal) * 100)
          : 0,
    },
    {
      name: 'Essay',
      value:
        qtTotal > 0 ? Math.round((analysis.question_types.essay / qtTotal) * 100) : 0,
    },
    {
      name: 'Calculation',
      value:
        qtTotal > 0
          ? Math.round((analysis.question_types.calculation / qtTotal) * 100)
          : 0,
    },
    {
      name: 'True/False',
      value:
        qtTotal > 0
          ? Math.round((analysis.question_types.true_false / qtTotal) * 100)
          : 0,
    },
  ].filter((d) => d.value > 0);

  // Topic distribution pie data
  const topicData = Object.entries(analysis.topic_distribution)
    .map(([name, value]) => ({
      name,
      value: Math.round(value * 100),
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);

  // Professor terms sorted by frequency
  const sortedTerms = [...analysis.professor_terms].sort(
    (a, b) => b.frequency - a.frequency
  );
  const maxFreq = sortedTerms[0]?.frequency || 1;

  return (
    <div className="space-y-8">
      {/* Top Concepts */}
      <div>
        <SectionTitle>Top Concepts by Importance</SectionTitle>
        {conceptData.length > 0 ? (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={conceptData}
                layout="vertical"
                margin={{ top: 0, right: 24, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis
                  type="number"
                  domain={[0, 1]}
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  tick={{ fontSize: 11 }}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={140}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip content={<BarTooltip />} />
                <Bar
                  dataKey="score"
                  fill="#3b82f6"
                  radius={[0, 4, 4, 0]}
                  maxBarSize={24}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-sm text-gray-400">No concept data available.</p>
        )}
        {/* Concept descriptions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-4">
          {analysis.top_concepts.slice(0, 6).map((c) => (
            <div key={c.concept} className="p-2.5 rounded-lg bg-blue-50 border border-blue-100">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-blue-800 truncate">
                  {c.concept}
                </span>
                <span className="text-xs text-blue-600 ml-2 flex-shrink-0">
                  ×{c.frequency}
                </span>
              </div>
              {c.description && (
                <p className="text-xs text-gray-600 line-clamp-2">{c.description}</p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Question Types + Topic Distribution */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Question Types */}
        <div>
          <SectionTitle>Question Type Distribution</SectionTitle>
          {questionTypeData.length > 0 ? (
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={questionTypeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={3}
                    dataKey="value"
                    label={({ name, value }) => `${value}%`}
                    labelLine={false}
                  >
                    {questionTypeData.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={PIE_COLORS[index % PIE_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<PieTooltipContent />} />
                  <Legend
                    iconType="circle"
                    iconSize={8}
                    wrapperStyle={{ fontSize: '11px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-gray-400">No question type data available.</p>
          )}
        </div>

        {/* Topic Distribution */}
        <div>
          <SectionTitle>Topic Distribution</SectionTitle>
          {topicData.length > 0 ? (
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={topicData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={3}
                    dataKey="value"
                    label={({ value }) => `${value}%`}
                    labelLine={false}
                  >
                    {topicData.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={PIE_COLORS[index % PIE_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<PieTooltipContent />} />
                  <Legend
                    iconType="circle"
                    iconSize={8}
                    wrapperStyle={{ fontSize: '11px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="text-sm text-gray-400">No topic data available.</p>
          )}
        </div>
      </div>

      {/* Professor's Favorite Terms */}
      {sortedTerms.length > 0 && (
        <div>
          <SectionTitle>Professor&apos;s Favorite Terms</SectionTitle>
          <div className="flex flex-wrap gap-2">
            {sortedTerms.slice(0, 30).map((term) => {
              const ratio = term.frequency / maxFreq;
              const fontSize =
                ratio > 0.8
                  ? 'text-xl'
                  : ratio > 0.6
                  ? 'text-lg'
                  : ratio > 0.4
                  ? 'text-base'
                  : ratio > 0.2
                  ? 'text-sm'
                  : 'text-xs';
              const opacity =
                ratio > 0.8
                  ? 'opacity-100'
                  : ratio > 0.5
                  ? 'opacity-90'
                  : ratio > 0.3
                  ? 'opacity-75'
                  : 'opacity-60';
              const colors = [
                'text-blue-600',
                'text-violet-600',
                'text-indigo-600',
                'text-sky-600',
              ];
              const color = colors[term.frequency % colors.length];
              return (
                <span
                  key={term.term}
                  title={term.context}
                  className={`${fontSize} ${opacity} ${color} font-medium cursor-default hover:opacity-100 transition-opacity px-1`}
                >
                  {term.term}
                </span>
              );
            })}
          </div>
          {/* Terms detail table */}
          <div className="mt-4 space-y-1">
            {sortedTerms.slice(0, 8).map((term) => (
              <div
                key={term.term}
                className="flex items-start gap-3 p-2 rounded-lg hover:bg-gray-50 text-sm"
              >
                <span className="font-medium text-gray-800 w-36 flex-shrink-0">
                  {term.term}
                </span>
                <span className="text-gray-500 flex-1 text-xs italic">
                  &ldquo;{term.context}&rdquo;
                </span>
                <span className="text-xs text-gray-400 flex-shrink-0">×{term.frequency}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
