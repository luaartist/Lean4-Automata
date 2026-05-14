import { APIError } from '@/lib/api/client';

interface ErrorStateProps {
  message: string;
  error?: unknown;
  onRetry?: () => void;
}

export function ErrorState({ message, error, onRetry }: ErrorStateProps) {
  const errorDetail = error instanceof APIError ? error.detail : 
    error instanceof Error ? error.message : 'Unknown error';

  return (
    <div className="flex items-center justify-center py-48">
      <div className="max-w-md bg-bg-surface border border-status-error rounded p-24 text-center">
        <svg
          className="w-48 h-48 text-status-error mx-auto mb-16"
          viewBox="0 0 48 48"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="24" cy="24" r="20" />
          <line x1="24" y1="14" x2="24" y2="28" />
          <circle cx="24" cy="34" r="2" fill="currentColor" />
        </svg>
        
        <h3 className="text-lg font-semibold mb-8">{message}</h3>
        <p className="text-sm text-text-secondary mb-16">{errorDetail}</p>
        
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-16 py-8 bg-accent-primary text-white rounded hover:bg-accent-hover transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
