'use client';
import { ResponsiveContainer, Treemap, Tooltip } from 'recharts';
import { getWeaknessColor } from '@/lib/utils';
import type { ConceptHeatmapItem } from '@/types';

interface ConceptHeatmapProps {
  data: ConceptHeatmapItem[];
}

interface TreemapNode {
  name: string;
  size: number;
  weakness_score: number;
  attempts: number;
  correct_count: number;
  incorrect_count: number;
}

interface CustomContentProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  weakness_score?: number;
}

function CustomContent(props: CustomContentProps) {
  const { x = 0, y = 0, width = 0, height = 0, name = '', weakness_score = 0 } = props;
  const fill = getWeaknessColor(weakness_score);

  if (width < 30 || height < 20) return null;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{ fill, stroke: '#fff', strokeWidth: 2, opacity: 0.9 }}
        rx={4}
      />
      {width > 60 && height > 30 && (
        <text
          x={x + width / 2}
          y={y + height / 2}
          textAnchor="middle"
          dominantBaseline="middle"
          style={{
            fontSize: Math.min(12, width / 8),
            fill: '#fff',
            fontWeight: 600,
            pointerEvents: 'none',
          }}
        >
          {name.length > width / 7 ? `${name.slice(0, Math.floor(width / 7))}…` : name}
        </text>
      )}
    </g>
  );
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: TreemapNode }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const item = payload[0].payload;
  const accuracy =
    item.attempts > 0
      ? Math.round((item.correct_count / item.attempts) * 100)
      : 0;

  return (
    <div className="bg-white border border-gray-200 shadow-lg rounded-xl p-3 text-sm max-w-[200px]">
      <p className="font-semibold text-gray-900 mb-2">{item.name}</p>
      <div className="space-y-1 text-xs">
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">Attempts</span>
          <span className="font-medium">{item.attempts}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">Accuracy</span>
          <span className="font-medium">{accuracy}%</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">Correct</span>
          <span className="font-medium text-green-600">{item.correct_count}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">Incorrect</span>
          <span className="font-medium text-red-600">{item.incorrect_count}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500">Weakness</span>
          <span
            className="font-medium"
            style={{ color: getWeaknessColor(item.weakness_score) }}
          >
            {Math.round(item.weakness_score * 100)}%
          </span>
        </div>
      </div>
    </div>
  );
}

export function ConceptHeatmap({ data }: ConceptHeatmapProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="p-4 bg-gray-100 rounded-full mb-4">
          <svg
            className="h-8 w-8 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
        </div>
        <p className="text-gray-600 font-medium">No heatmap data yet</p>
        <p className="text-sm text-gray-400 mt-1">
          Take an exam to see your concept weakness heatmap
        </p>
      </div>
    );
  }

  const treemapData: TreemapNode[] = data.map((item) => ({
    name: item.concept,
    size: Math.max(item.attempts, 1),
    weakness_score: item.weakness_score,
    attempts: item.attempts,
    correct_count: item.correct_count,
    incorrect_count: item.incorrect_count,
  }));

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex items-center gap-6 text-xs text-gray-500">
        <span className="font-medium text-gray-700">Weakness Score:</span>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-green-500 inline-block" />
          <span>Strong (&lt;20%)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-yellow-400 inline-block" />
          <span>Fair (20–40%)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-orange-500 inline-block" />
          <span>Weak (40–70%)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-red-500 inline-block" />
          <span>Critical (&gt;70%)</span>
        </div>
        <span className="ml-auto text-gray-400">Block size = # attempts</span>
      </div>

      {/* Treemap */}
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={treemapData}
            dataKey="size"
            aspectRatio={4 / 3}
            content={<CustomContent />}
          >
            <Tooltip content={<CustomTooltip />} />
          </Treemap>
        </ResponsiveContainer>
      </div>

      {/* Sorted list */}
      <div className="space-y-2">
        <p className="text-sm font-semibold text-gray-700">
          Concepts Ranked by Weakness
        </p>
        {[...data]
          .sort((a, b) => b.weakness_score - a.weakness_score)
          .map((item) => {
            const accuracy =
              item.attempts > 0
                ? Math.round((item.correct_count / item.attempts) * 100)
                : 0;
            return (
              <div
                key={item.concept}
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50"
              >
                <div
                  className="w-3 h-3 rounded-sm flex-shrink-0"
                  style={{ backgroundColor: getWeaknessColor(item.weakness_score) }}
                />
                <span className="text-sm text-gray-700 flex-1 min-w-0 truncate">
                  {item.concept}
                </span>
                <span className="text-xs text-gray-500 flex-shrink-0">
                  {item.attempts} attempts
                </span>
                <span className="text-xs font-medium flex-shrink-0 w-12 text-right">
                  {accuracy}% acc
                </span>
              </div>
            );
          })}
      </div>
    </div>
  );
}
