import { type MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import { Link } from "react-router-dom";
import CaseStatusPill from "../cases/CaseStatusPill";
import type { CaseStatus } from "../cases/caseStatus";
import formatDate from "../cases/formatDate";
import getCasePath from "../cases/getCasePath";
import listQueue, { type QueuePayload } from "./listQueue";
import triage, { tiers, type Tier, type TriagedCase } from "./triage";

const tierInfo: Record<Tier, { title: string; description: string }> = {
  decision: { title: "Needs your decision", description: "Checks are done. Blocking findings first." },
  waiting: { title: "Waiting on client", description: "Documents or answers to your questions are outstanding." },
  processing: { title: "Processing", description: "Intake, checks or the legacy write are running. No action needed." },
  done: { title: "Completed", description: "The legacy app confirmed the write." },
};

const statusAction: Record<CaseStatus, string> = {
  open: "Chase the client for documents",
  intake_in_progress: "None, OCR and sorting are running",
  evaluating: "None, checks are running",
  awaiting_decision: "Approve or return the case",
  awaiting_clarification: "Wait for the client's answer",
  approved: "None, writing to the legacy app",
  completed: "",
};

const nextAction = (c: TriagedCase) => c.findings[0]?.action ?? statusAction[c.status];

// The app runs inside the host's router, which swallows plain "#hash" navigation, so scroll by hand.
function jumpToTier(event: MouseEvent<HTMLAnchorElement>) {
  const section = document.getElementById(event.currentTarget.hash.slice(1));
  if (!section) return;
  event.preventDefault();
  section.querySelector("details")?.setAttribute("open", "");
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

function QueueTable({ cases, rank }: { cases: TriagedCase[]; rank: Map<string, number> }) {
  return (
    <div className="bo-table-wrap">
      <table className="bo-table bo-table--queue">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Client</th>
            <th scope="col">Issues</th>
            <th scope="col">Next action</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => (
            <tr key={c.case_id}>
              <td className="bo-queue__rank">{rank.get(c.case_id)}</td>
              <td>
                <span className="bo-table__strong">{c.client?.name ?? "Unknown client"}</span>
                <span className="bo-table__meta">{c.client ? `IČO ${c.client.ico}` : c.case_found ? "Not in the client registry" : "Case not in the case registry"}</span>
                <CaseStatusPill status={c.status} />
                <span className="bo-table__meta">
                  {[
                    c.created_at && `opened ${formatDate(c.created_at)}`,
                    c.evaluation.started_at && `checked ${formatDate(c.evaluation.started_at)}`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </td>
              <td>
                {c.findings.length === 0 ? (
                  <span className="bo-table__meta">No issues found</span>
                ) : (
                  <ul className="bo-queue__findings">
                    {c.findings.map((f) => (
                      <li key={f.title}>
                        <span className={`bo-queue__severity bo-queue__severity--${f.severity}`}>
                          {f.severity === "blocking" ? "Blocking" : "Material"}
                        </span>
                        <span className="bo-queue__finding-title">{f.title}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </td>
              <td className="bo-queue__action">
                {nextAction(c) || "—"}
                <Link className="bo-link bo-queue__review" to={getCasePath(c.case_id)}>
                  Open case review
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function QueuePage() {
  const { api, track } = useWonderful();
  const apiRef = useRef(api);
  apiRef.current = api;
  const trackRef = useRef(track);
  trackRef.current = track;
  const opened = useRef(false);
  const [payload, setPayload] = useState<QueuePayload>();
  const [error, setError] = useState(false);

  const request = useRef(0);

  // Only the latest load shows, even when an earlier one answers later.
  const load = useCallback(() => {
    const current = ++request.current;
    setError(false);
    setPayload(undefined);
    listQueue(apiRef.current).then(
      (result) => current === request.current && setPayload(result),
      () => current === request.current && setError(true),
    );
  }, []);

  useEffect(() => {
    if (!opened.current) {
      opened.current = true;
      trackRef.current("queue_opened");
    }
    load();
  }, [load]);

  const queue = useMemo(() => (payload ? triage(payload.cases) : undefined), [payload]);

  if (error) {
    return (
      <>
        <h1 className="bo-title">Work queue</h1>
        <div className="bo-card bo-empty" role="alert">
          <p>The work queue could not be loaded.</p>
          <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={load}>
            Try again
          </button>
        </div>
      </>
    );
  }
  if (!payload || !queue) {
    return (
      <>
        <h1 className="bo-title">Work queue</h1>
        <p className="bo-empty" aria-busy="true">
          Loading cases…
        </p>
      </>
    );
  }

  const byTier = tiers.map((tier) => ({ tier, cases: queue.filter((c) => c.tier === tier) }));
  const rank = new Map(queue.map((c, i) => [c.case_id, i + 1]));
  const active = queue.filter((c) => c.tier !== "done").length;

  return (
    <>
      <div className="bo-heading bo-heading--compact">
        <h1 className="bo-title">Work queue</h1>
        <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={load}>
          Refresh
        </button>
      </div>
      <p className="bo-queue__lead">
        {active} active {active === 1 ? "case" : "cases"} with a check run, most acute first.
        {payload.truncated && " The list was cut short, so not every case is shown."}
      </p>

      <ul className="bo-queue__summary" aria-label="Queue summary">
        {byTier.map(({ tier, cases }) => (
          <li key={tier}>
            <a className={`bo-queue__tile bo-queue__tile--${tier}`} href={`#queue-${tier}`} onClick={jumpToTier}>
              <span className="bo-queue__tile-count">{cases.length}</span>
              <span className="bo-queue__tile-title">{tierInfo[tier].title}</span>
            </a>
          </li>
        ))}
      </ul>

      {byTier.map(({ tier, cases }) => {
        const head = (
          <header className="bo-queue__section-head">
            <span className={`bo-queue__dot bo-queue__dot--${tier}`} aria-hidden="true" />
            <h2 id={`queue-${tier}-title`} className="bo-queue__section-title">
              {tierInfo[tier].title} <span className="bo-queue__section-count">{cases.length}</span>
            </h2>
            <p className="bo-queue__section-description">{tierInfo[tier].description}</p>
          </header>
        );
        const body =
          cases.length === 0 ? <p className="bo-empty">Nothing here.</p> : <QueueTable cases={cases} rank={rank} />;
        return (
          <section key={tier} id={`queue-${tier}`} className="bo-card bo-card--queue" aria-labelledby={`queue-${tier}-title`}>
            {tier === "done" ? (
              <details className="bo-queue__done">
                <summary>{head}</summary>
                {body}
              </details>
            ) : (
              <>
                {head}
                {body}
              </>
            )}
          </section>
        );
      })}
    </>
  );
}
