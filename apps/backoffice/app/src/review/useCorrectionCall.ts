import { useCallback, useEffect, useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";

const pollMs = 4000;
// A call that hasn't finished after this long dropped before the agent was done.
const staleMs = 10 * 60 * 1000;

export type CorrectionCall = { request_id: string; status: string; requested_at: string; requested_by: string | null };

const activeStatuses = new Set(["pending", "in_call", "verified"]);

export function isActive(call: CorrectionCall | null): boolean {
  return !!call && activeStatuses.has(call.status) && Date.now() - Date.parse(call.requested_at) < staleMs;
}

/** What the reviewer sees about the case's latest correction call. */
export function describeCall(call: CorrectionCall): { text: string; tone: "info" | "success" | "error" } {
  if (activeStatuses.has(call.status) && !isActive(call)) return { text: "The call ended before the client was informed.", tone: "error" };
  switch (call.status) {
    case "pending":
      return { text: "Calling the client…", tone: "info" };
    case "in_call":
      return { text: "On the call, verifying the client…", tone: "info" };
    case "verified":
      return { text: "Client verified, explaining the corrections…", tone: "info" };
    case "email_sent":
      return { text: "Client informed. The findings and upload link were emailed.", tone: "success" };
    case "verification_failed":
      return { text: "The surname didn't match, so nothing was shared.", tone: "error" };
    case "ended_unverified":
      return { text: "The call ended before the client was verified. Nothing was shared.", tone: "error" };
    case "ended":
      return { text: "The call ended before the email was sent.", tone: "error" };
    default:
      return { text: "The call couldn't be placed.", tone: "error" };
  }
}

/** The case's latest correction call, polled while the agent is still on it. */
export default function useCorrectionCall(caseId: string) {
  const { api } = useWonderful();
  const [call, setCall] = useState<CorrectionCall | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    // The plain Vite dev server has no Wonderful host to ask.
    if (import.meta.env.DEV) return;
    let cancelled = false;
    let timer: number | undefined;
    const load = () =>
      api
        .invokeFunction<{ call: CorrectionCall | null }>("backoffice/correction-call-status", { method: "POST", params: { case_id: caseId } })
        .then(({ call: latest }) => {
          if (cancelled) return;
          setCall(latest);
          if (isActive(latest)) timer = window.setTimeout(load, pollMs);
        })
        .catch(() => {
          if (!cancelled) timer = window.setTimeout(load, pollMs);
        });
    load();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [api, caseId, version]);

  return { call, refresh: useCallback(() => setVersion((v) => v + 1), []) };
}
