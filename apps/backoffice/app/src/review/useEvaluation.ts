import { useEffect, useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import type { EvaluationPayload, EvaluationRow, ResultRow } from "./evaluation";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; payload: EvaluationPayload };

type Loader = (evaluationId: string | null) => Promise<EvaluationPayload>;

// The plain Vite dev server has no Wonderful host, so it reads a snapshot of both
// tables exported with `wful tables row-list` (dev/public/mock-case/evaluations.json).
async function loadSnapshot(evaluationId: string | null): Promise<EvaluationPayload> {
  const res = await fetch("/mock-case/evaluations.json");
  if (!res.ok) throw new Error(`snapshot request failed: ${res.status}`);
  const snapshot = (await res.json()) as { evaluations: EvaluationRow[]; results: ResultRow[] };
  const evaluation = evaluationId
    ? (snapshot.evaluations.find((e) => e.evaluation_id === evaluationId) ?? null)
    : (snapshot.evaluations[0] ?? null);
  return {
    evaluation,
    evaluations: snapshot.evaluations,
    results: snapshot.results.filter((r) => r.evaluation_id === evaluation?.evaluation_id),
  };
}

function useHostLoader(): Loader {
  const { api } = useWonderful();
  return (evaluationId) =>
    api.invokeFunction<EvaluationPayload>("backoffice/evaluation-get", {
      method: "POST",
      params: evaluationId ? { evaluation_id: evaluationId } : {},
    });
}

// import.meta.env.DEV is a build-time constant, so the hook order never changes.
const useLoader: () => Loader = import.meta.env.DEV ? () => loadSnapshot : useHostLoader;

export default function useEvaluation(evaluationId: string | null): State {
  const load = useLoader();
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    load(evaluationId)
      .then((payload) => !cancelled && setState({ status: "ready", payload }))
      .catch((e: unknown) => !cancelled && setState({ status: "error", message: e instanceof Error ? e.message : String(e) }));
    return () => {
      cancelled = true;
    };
    // `load` is recreated each render; only the requested id should refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [evaluationId]);

  return state;
}
