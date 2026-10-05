/** Minimal data-fetching hook built on lib/api.ts. Pass `null` to skip fetching. */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "./api";

export interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  setData: (updater: T | null | ((prev: T | null) => T | null)) => void;
}

export function useFetch<T>(path: string | null): FetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(path !== null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const requestId = useRef(0);

  useEffect(() => {
    if (path === null) {
      setLoading(false);
      return;
    }
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    api
      .get<T>(path)
      .then((res) => {
        if (id === requestId.current) setData(res);
      })
      .catch((err: unknown) => {
        if (id === requestId.current) setError(errorMessage(err, "Failed to load data."));
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false);
      });
  }, [path, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  return { data, loading, error, reload, setData };
}
