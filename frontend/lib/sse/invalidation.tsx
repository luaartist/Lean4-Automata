'use client';

import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { InvalidationPayload } from '../api/types';

const SSE_ENDPOINT = '/api/v1/events/invalidation';
const MAX_BACKOFF_MS = 30_000;
const HEARTBEAT_TIMEOUT_MS = 5_000;

export function InvalidationProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<Date | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const backoffRef = useRef(1000);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const clearHeartbeatTimeout = () => {
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current);
      heartbeatTimeoutRef.current = null;
    }
  };

  const startHeartbeatTimeout = () => {
    clearHeartbeatTimeout();
    heartbeatTimeoutRef.current = setTimeout(() => {
      setIsConnected(false);
    }, HEARTBEAT_TIMEOUT_MS);
  };

  const connect = () => {
    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    try {
      const es = new EventSource(SSE_ENDPOINT);
      eventSourceRef.current = es;

      es.onopen = () => {
        setIsConnected(true);
        backoffRef.current = 1000; // Reset backoff on successful connection
        startHeartbeatTimeout();
      };

      es.addEventListener('invalidation', (event) => {
        try {
          const payload: InvalidationPayload = JSON.parse((event as MessageEvent).data);
          const now = new Date();
          setLastEvent(now);
          startHeartbeatTimeout();

          // Invalidate matching queries per UX spec §6
          const { file_id, symbols } = payload;

          // Invalidate dependency graphs (all variants)
          queryClient.invalidateQueries({ queryKey: ['deps'] });

          // Invalidate file-scoped queries
          if (file_id != null) {
            queryClient.invalidateQueries({ queryKey: ['file', file_id] });
            queryClient.invalidateQueries({ queryKey: ['modules', 'metrics'] });
          }

          // Invalidate specific symbols
          if (symbols && Array.isArray(symbols)) {
            symbols.forEach((fullName) => {
              queryClient.invalidateQueries({ queryKey: ['symbols', fullName] });
            });
          }
        } catch (err) {
          console.warn('[SSE] Failed to parse invalidation payload:', err);
        }
      });

      // Handle heartbeat comments (keep connection alive)
      es.onmessage = () => {
        startHeartbeatTimeout();
      };

      es.onerror = () => {
        setIsConnected(false);
        clearHeartbeatTimeout();
        es.close();
        eventSourceRef.current = null;

        // Exponential backoff reconnect
        const backoff = backoffRef.current;
        backoffRef.current = Math.min(backoff * 2, MAX_BACKOFF_MS);

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, backoff);
      };
    } catch (err) {
      console.error('[SSE] Failed to create EventSource:', err);
      setIsConnected(false);
    }
  };

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      clearHeartbeatTimeout();
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [queryClient]);

  // Expose connection state for SSEIndicator component
  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as any).__sseConnectionState = {
        connected: isConnected,
        lastEvent,
      };
    }
  }, [isConnected, lastEvent]);

  return <>{children}</>;
}
