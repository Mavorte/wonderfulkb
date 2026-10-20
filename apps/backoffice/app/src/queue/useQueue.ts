import { useCallback, useEffect, useRef, useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import listQueue, { type QueuePayload } from "./listQueue";

export type QueueState = {
  payload: QueuePayload | undefined;
  error: boolean;
  // Reloads from scratch, showing the loading state.
  load: () => void;
  // Reloads in the background; the current list stays until the new one arrives.
  refresh: () => void;
};

type Loader = { loadQueue: () => Promise<QueuePayload>; track: (name: string) => void };

// Case statuses change while the queue is open (evaluator runs finish, cases move
// along the lifecycle), so the queue reloads itself while the page is visible.
const refreshMs = 10000;

// The plain Vite dev server has no Wonderful host, so it reads a snapshot of the
// case-queue response (dev/public/mock-case/queue.json).
async function loadSnapshot(): Promise<QueuePayload> {
  const res = await fetch("/mock-case/queue.json");
  if (!res.ok) throw new Error(`snapshot request failed: ${res.status}`);
  return (await res.json()) as QueuePayload;
}

const snapshotLoader: Loader = { loadQueue: loadSnapshot, track: () => {} };

function useHostLoader(): Loader {
  const { api, track } = useWonderful();
  return { loadQueue: () => listQueue(api), track };
}

// import.meta.env.DEV is a build-time constant, so the hook order never changes.
const useLoader: () => Loader = import.meta.env.DEV ? () => snapshotLoader : useHostLoader;

/** Loads the work queue and keeps it current; only the latest load shows, even when an earlier one answers later. */
export default function useQueue(): QueueState {
  const loader = useLoader();
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const opened = useRef(false);
  const request = useRef(0);
  const loading = useRef(false);
  const [payload, setPayload] = useState<QueuePayload>();
  const [error, setError] = useState(false);

  const fetchQueue = useCallback((silent: boolean) => {
    // A background refresh never replaces a full load that is still answering.
    if (silent && loading.current) return;
    const current = ++request.current;
    if (!silent) {
      loading.current = true;
      setError(false);
      setPayload(undefined);
    }
    loaderRef.current
      .loadQueue()
      .then(
        (result) => {
          if (current !== request.current) return;
          setError(false);
          setPayload(result);
        },
        // A failed background refresh keeps the list already on screen.
        () => current === request.current && !silent && setError(true),
      )
      .finally(() => {
        if (current === request.current) loading.current = false;
      });
  }, []);

  const load = useCallback(() => fetchQueue(false), [fetchQueue]);
  const refresh = useCallback(() => fetchQueue(true), [fetchQueue]);

  useEffect(() => {
    if (!opened.current) {
      opened.current = true;
      loaderRef.current.track("queue_opened");
    }
    load();
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(() => document.visibilityState === "visible" && refresh(), refreshMs);
    const onVisible = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]);

  return { payload, error, load, refresh };
}
