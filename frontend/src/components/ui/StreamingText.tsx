'use client';
import { useEffect, useState, useRef } from 'react';

interface StreamingTextProps {
  text: string;
  isStreaming: boolean;
  className?: string;
  speed?: number;
}

export function StreamingText({
  text,
  isStreaming,
  className = '',
  speed = 8,
}: StreamingTextProps) {
  const [displayedText, setDisplayedText] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  const indexRef = useRef(0);
  const prevTextRef = useRef('');

  useEffect(() => {
    // If text was reset, restart from beginning
    if (text.length < prevTextRef.current.length) {
      setDisplayedText('');
      indexRef.current = 0;
    }
    prevTextRef.current = text;

    if (indexRef.current >= text.length) return;

    const interval = setInterval(() => {
      if (indexRef.current < text.length) {
        const charsToAdd = Math.min(speed, text.length - indexRef.current);
        setDisplayedText(text.slice(0, indexRef.current + charsToAdd));
        indexRef.current += charsToAdd;
      } else {
        clearInterval(interval);
      }
    }, 16);

    return () => clearInterval(interval);
  }, [text, speed]);

  // Cursor blink effect
  useEffect(() => {
    if (!isStreaming && indexRef.current >= text.length) {
      setShowCursor(false);
      return;
    }
    const blink = setInterval(() => setShowCursor((prev) => !prev), 530);
    return () => clearInterval(blink);
  }, [isStreaming, text.length]);

  return (
    <div className={`font-mono text-sm leading-relaxed whitespace-pre-wrap ${className}`}>
      {displayedText}
      {(isStreaming || indexRef.current < text.length) && (
        <span
          className={`inline-block w-0.5 h-4 bg-blue-600 ml-0.5 align-text-bottom transition-opacity ${
            showCursor ? 'opacity-100' : 'opacity-0'
          }`}
        />
      )}
    </div>
  );
}
