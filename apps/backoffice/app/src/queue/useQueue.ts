import { useCallback, useEffect, useRef, useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import listQueue, { type QueuePayload } from "./listQueue";

export type QueueState = { payload: QueuePayload | undefined; error: boolean; load: () => void };

type Loader = { loadQueue: () => Promise<QueuePayload>; track: (name: string) => void };

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

/** Loads the work queue once; only the latest load shows, even when an earlier one answers later. */
export default function useQueue(): QueueState {
  const loader = useLoader();
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const opened = useRef(false);
  const request = useRef(0);
  const [payload, setPayload] = useState<QueuePayload>();
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    const current = ++request.current;
    setError(false);
    setPayload(undefined);
    loaderRef.current.loadQueue().then(
      (result) => current === request.current && setPayload(result),
      () => current === request.current && setError(true),
    );
  }, []);

  useEffect(() => {
    if (!opened.current) {
      opened.current = true;
      loaderRef.current.track("queue_opened");
    }
    load();
  }, [load]);

  return { payload, error, load };
}
