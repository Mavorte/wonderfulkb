import { useEffect, useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import type { EvaluationPayload, EvaluationRow, ResultRow } from "./evaluation";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; payload: EvaluationPayload };

/** A specific run, else the latest run of the case, else the latest run overall. */
export type EvaluationRequest = { caseId: string | null; evaluationId: string | null };

type Loader = (request: EvaluationRequest) => Promise<EvaluationPayload>;

// The plain Vite dev server has no Wonderful host, so it reads a snapshot of both
// tables exported with `wful tables row-list` (dev/public/mock-case/evaluations.json).
async function loadSnapshot({ caseId, evaluationId }: EvaluationRequest): Promise<EvaluationPayload> {
  const res = await fetch("/mock-case/evaluations.json");
  if (!res.ok) throw new Error(`snapshot request failed: ${res.status}`);
  const snapshot = (await res.json()) as { evaluations: EvaluationRow[]; results: ResultRow[] };
  // Like evaluation-get, the snapshot lists runs newest first.
  const evaluation =
    snapshot.evaluations.find((e) =>
      evaluationId ? e.evaluation_id === evaluationId : !caseId || e.case_id === caseId,
    ) ?? null;
  return {
    evaluation,
    results: snapshot.results.filter((r) => r.evaluation_id === evaluation?.evaluation_id),
  };
}

function useHostLoader(): Loader {
  const { api } = useWonderful();
  return ({ caseId, evaluationId }) =>
    api.invokeFunction<EvaluationPayload>("backoffice/evaluation-get", {
      method: "POST",
      params: evaluationId ? { evaluation_id: evaluationId } : caseId ? { case_id: caseId } : {},
    });
}

// import.meta.env.DEV is a build-time constant, so the hook order never changes.
const useLoader: () => Loader = import.meta.env.DEV ? () => loadSnapshot : useHostLoader;

export default function useEvaluation({ caseId, evaluationId }: EvaluationRequest): State {
  const load = useLoader();
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    load({ caseId, evaluationId })
      .then((payload) => !cancelled && setState({ status: "ready", payload }))
      .catch((e: unknown) => !cancelled && setState({ status: "error", message: e instanceof Error ? e.message : String(e) }));
    return () => {
      cancelled = true;
    };
    // `load` is recreated each render; only the requested ids should refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, evaluationId]);

  return state;
}
