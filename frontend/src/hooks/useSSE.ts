'use client';
import { useState, useCallback, useEffect, useRef } from 'react';
import Cookies from 'js-cookie';
import { extractErrorMessage } from '@/lib/api';

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
      controllerRef.current?.abort();
      const token = Cookies.get('access_token');
      const controller = new AbortController();
      controllerRef.current = controller;
      setIsStreaming(true);
      setTokensUsed(0);
      let streamCompleted = false;
      let streamErrored = false;

      try {
        const response = await fetch(url, {
          method: options.method || 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: options.body ? JSON.stringify(options.body) : undefined,
          signal: controller.signal,
        });

        if (!response.ok) {
          let detail = `Request failed with status ${response.status}.`;
          try {
            const payload = await response.json();
            if (typeof payload?.detail === 'string') detail = payload.detail;
          } catch {
            // keep status fallback
          }
          throw new Error(extractErrorMessage(new Error(detail), detail));
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
                if (data.type === 'complete') {
                  streamCompleted = true;
                  options.onComplete?.();
                }
                if (data.type === 'error') {
                  streamErrored = true;
                  options.onError?.(data.error || data.content || 'Unknown error');
                }
              } catch {
                // ignore parse errors for malformed SSE lines
              }
            }
          }
        }

        if (!streamCompleted && !streamErrored && !controller.signal.aborted) {
          options.onError?.('The AI request ended before it completed. Please try again.');
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          options.onError?.(err.message);
        }
      } finally {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
          setIsStreaming(false);
        }
      }
    },
    []
  );

  const stopStream = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setIsStreaming(false);
  }, []);

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  return { isStreaming, tokensUsed, startStream, stopStream };
}
