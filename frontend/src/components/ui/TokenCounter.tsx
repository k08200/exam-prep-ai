'use client';
import { formatTokens } from '@/lib/utils';

interface TokenCounterProps {
  tokens: number;
  label?: string;
  animated?: boolean;
}

export function TokenCounter({
  tokens,
  label = 'Tokens used',
  animated = true,
}: TokenCounterProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-violet-50 border border-violet-200 rounded-full">
      <div
        className={`w-2 h-2 rounded-full bg-violet-500 ${
          animated && tokens > 0 ? 'animate-pulse' : ''
        }`}
      />
      <span className="text-xs font-mono text-violet-700 font-medium">
        {label}: {formatTokens(tokens)}
      </span>
    </div>
  );
}
