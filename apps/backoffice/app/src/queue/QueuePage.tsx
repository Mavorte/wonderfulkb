import { useMemo } from "react";
import CaseStatusPill from "../cases/CaseStatusPill";
import formatDate from "../cases/formatDate";
import mockStatuses from "./mockStatuses";
import snapshot from "./uwCases.snapshot.json";
import triage, { tiers, type CaseStatus, type QueueCase, type Tier, type TriagedCase } from "./triage";

// Local mock: a snapshot of the wonderfulkb-uw-cases table joined with its
// clients, documents and document-analysis rows, taken on 19 Oct 2026.
const snapshotDate = "19 Oct 2026";

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
                <span className="bo-table__meta">{c.client ? `IČO ${c.client.ico}` : "Not in the client registry"}</span>
                <CaseStatusPill status={c.status} />
                <span className="bo-table__meta">
                  {c.documents.length}
                  {c.expected_documents.length > 0 ? ` / ${c.expected_documents.length}` : ""} docs · opened{" "}
                  {formatDate(c.created_at)}
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
                        <span className="bo-table__meta">{f.detail}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </td>
              <td className="bo-queue__action">{nextAction(c) || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function QueuePage() {
  const queue = useMemo(
    () =>
      triage(
        (snapshot as QueueCase[]).map((c) => ({ ...c, status: mockStatuses[c.case_id] ?? c.status })),
      ),
    [],
  );
  const byTier = tiers.map((tier) => ({ tier, cases: queue.filter((c) => c.tier === tier) }));
  const rank = new Map(queue.map((c, i) => [c.case_id, i + 1]));
  const active = queue.filter((c) => c.tier !== "done").length;

  return (
    <>
      <div className="bo-heading bo-heading--compact">
        <h1 className="bo-title">Work queue</h1>
      </div>
      <p className="bo-queue__lead">
        {active} active cases, most acute first. Mock data from <code>wonderfulkb-uw-cases</code>, snapshot of{" "}
        {snapshotDate}.
      </p>

      <ul className="bo-queue__summary" aria-label="Queue summary">
        {byTier.map(({ tier, cases }) => (
          <li key={tier}>
            <a className={`bo-queue__tile bo-queue__tile--${tier}`} href={`#queue-${tier}`}>
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
