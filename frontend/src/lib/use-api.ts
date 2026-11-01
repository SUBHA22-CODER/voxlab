"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseApiOptions {
  /** Polling interval in ms; 0 disables polling. */
  pollMs?: number;
  enabled?: boolean;
}

/**
 * Minimal fetch-state hook with stable refs (no infinite-loop footgun) and
 * optional polling — used for live run status without a heavier data lib.
 */
export function useApi<T>(fetcher: () => Promise<T>, options: UseApiOptions = {}) {
  const { pollMs = 0, enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const refetch = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    refetch();
    if (pollMs <= 0) return;
    const id = setInterval(refetch, pollMs);
    return () => clearInterval(id);
  }, [enabled, pollMs, refetch]);

  return { data, error, loading, refetch };
}
