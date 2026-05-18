'use client';
import { useState, useCallback, useRef } from 'react';
import Cookies from 'js-cookie';

interface SSEEvent {
  type: string;
  content?: string;
  tokens_used?: number;
  question?: Record<string, unknown>;
  exam_id?: string;
  total_tokens?: number;
  analysis?: Record<string, unknown>;
  error?: string;
}

export function useSSE() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [tokensUsed, setTokensUsed] = useState(0);
  const controllerRef = useRef<AbortController | null>(null);

  const startStream = useCallback(
    async (
      url: string,
      options: {
        method?: string;
        body?: Record<string, unknown>;
        onEvent: (event: SSEEvent) => void;
        onComplete?: () => void;
        onError?: (error: string) => void;
      }
    ) => {
      const token = Cookies.get('access_token');
      controllerRef.current = new AbortController();
      setIsStreaming(true);
      setTokensUsed(0);

      try {
        const response = await fetch(url, {
          method: options.method || 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: options.body ? JSON.stringify(options.body) : undefined,
          signal: controllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        if (!reader) throw new Error('No response body');

        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data: SSEEvent = JSON.parse(line.slice(6));
                if (data.tokens_used) {
                  setTokensUsed((prev) => Math.max(prev, data.tokens_used!));
                }
                if (data.total_tokens) {
                  setTokensUsed(data.total_tokens);
                }
                options.onEvent(data);
                if (data.type === 'complete') options.onComplete?.();
                if (data.type === 'error') {
                  options.onError?.(data.error || data.content || 'Unknown error');
                }
              } catch {
                // ignore parse errors for malformed SSE lines
              }
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          options.onError?.(err.message);
        }
      } finally {
        setIsStreaming(false);
      }
    },
    []
  );

  const stopStream = useCallback(() => {
    controllerRef.current?.abort();
    setIsStreaming(false);
  }, []);

  return { isStreaming, tokensUsed, startStream, stopStream };
}
