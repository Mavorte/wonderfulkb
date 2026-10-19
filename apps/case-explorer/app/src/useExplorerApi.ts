import { useWonderful } from "@wonderful/app-sdk";
import { useCallback, useEffect, useRef, useState } from "react";
import type { UpstreamResult } from "./types";

const APP_SLUG = "case-explorer";

export type FunctionCall = <T>(slug: string, params?: Record<string, unknown>) => Promise<UpstreamResult<T>>;

// Calls an explorer Function. A failed invoke (network, 403) becomes a result
// with status 0, so callers handle one shape.
export function useExplorerApi(): FunctionCall {
  const { api } = useWonderful();
  const apiRef = useRef(api);
  apiRef.current = api;
  return useCallback(async <T,>(slug: string, params: Record<string, unknown> = {}) => {
    try {
      return await apiRef.current.invokeFunction<UpstreamResult<T>>(`${APP_SLUG}/${slug}`, { method: "POST", params });
    } catch (error) {
      return {
        url: "",
        status: 0,
        ok: false,
        body: null,
        error: `calling Function ${slug} failed: ${error instanceof Error ? error.message : String(error)}`,
      } satisfies UpstreamResult<T>;
    }
  }, []);
}

export type Loadable<T> = { isLoading: boolean; result: UpstreamResult<T> | null; reload: () => void };

// Loads a Function result whenever `params` changes; `params: null` means nothing to load.
export function useFunctionResult<T>(slug: string, params: Record<string, unknown> | null): Loadable<T> {
  const call = useExplorerApi();
  const [state, setState] = useState<{ isLoading: boolean; result: UpstreamResult<T> | null }>({
    isLoading: false,
    result: null,
  });
  const [version, setVersion] = useState(0);
  const key = params ? JSON.stringify(params) : null;

  useEffect(() => {
    if (key === null) {
      setState({ isLoading: false, result: null });
      return;
    }
    let isCurrent = true;
    setState((previous) => ({ ...previous, isLoading: true }));
    call<T>(slug, JSON.parse(key)).then((result) => {
      if (isCurrent) setState({ isLoading: false, result });
    });
    return () => {
      isCurrent = false;
    };
  }, [call, slug, key, version]);

  return { ...state, reload: () => setVersion((v) => v + 1) };
}
