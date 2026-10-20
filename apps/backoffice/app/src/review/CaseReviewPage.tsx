import { useMemo, useState } from "react";
import Skeleton from "../Skeleton";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import ActivityTimeline from "./ActivityTimeline";
import DecisionPanel from "./DecisionPanel";
import DocumentPanel, { type Focus } from "./DocumentPanel";
import EvidenceChip from "./EvidenceChip";
import StatusIcon from "./StatusIcon";
import {
  createCaseView,
  groupSources,
  formatDuration,
  formatTime,
  type CaseView,
  type CheckStatus,
  type RuleGroup,
  type RuleView,
} from "./evaluation";
import { rawStatusLabel } from "./ruleLabels";
import getCasePath from "../cases/getCasePath";
import useDocumentPreviews from "./useDocumentPreviews";
import useEvaluation from "./useEvaluation";

type Tab = "rules" | "activity";

const verdictLabel: Record<string, string> = {
  needs_correction: "Needs correction",
  ready: "Ready",
  approved: "Ready",
  rejected: "Rejected",
};

function countRules(rules: RuleView[], status: CheckStatus) {
  return rules.filter((r) => r.status === status).length;
}

function rawCounts(rules: RuleView[]) {
  const counts = new Map<string, number>();
  for (const r of rules) counts.set(r.rawStatus, (counts.get(r.rawStatus) ?? 0) + 1);
  return [...counts.entries()];
}

function RuleRow({ rule, onOpen }: { rule: RuleView; onOpen: (focus: Focus) => void }) {
  return (
    <li className={`cr-finding cr-finding--${rule.status}`} id={`rule-${rule.id}`}>
      <StatusIcon status={rule.status} size={16} />
      <div className="cr-finding__body">
        <p className="cr-finding__title">
          {rule.label}
          <span className={`cr-raw cr-raw--${rule.status}`}>{rawStatusLabel[rule.rawStatus] ?? rule.rawStatus}</span>
        </p>
        <div className="cr-finding__more">
          <p className="cr-finding__detail">{rule.reasoning}</p>
          {rule.expected && (
            <p className="cr-finding__expected">
              <span>Expected</span> {rule.expected}
            </p>
          )}
          {rule.signatures.length > 0 && (
            <ul className="cr-sigs">
              {rule.signatures.map((s) => (
                <li key={s.role}>
                  <StatusIcon status={s.found >= s.required ? "pass" : "fail"} size={16} />
                  {s.role} signature {s.found}/{s.required}
                  {s.pages.length > 0 && <span className="cr-muted"> · p. {s.pages.join(", ")}</span>}
                </li>
              ))}
            </ul>
          )}
          {rule.confidence !== null && (
            <p className="cr-muted cr-finding__conf">Extraction confidence {Math.round(rule.confidence * 100)} %</p>
          )}
        </div>
        {rule.sources.length > 0 && (
          <div className="cr-finding__evidence">
            {groupSources(rule.sources).map((s) => (
              <EvidenceChip key={s.docKey} source={s} onOpen={onOpen} />
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

function GroupCard({
  group,
  open,
  onToggle,
  onOpen,
}: {
  group: RuleGroup;
  open: boolean;
  onToggle: () => void;
  onOpen: (focus: Focus) => void;
}) {
  const [showRest, setShowRest] = useState(false);
  if (!group.evaluated) {
    return (
      <li className="cr-rule cr-rule--disabled" aria-disabled="true">
        <div className="cr-rule__head">
          <span className="cr-rule__no">{group.id}</span>
          <span className="cr-rule__text">
            <span className="cr-rule__title" title={group.description}>
              {group.title}
            </span>
            <span className="cr-rule__counts">Not evaluated by the agent yet</span>
          </span>
          <span />
          <span />
        </div>
      </li>
    );
  }
  const issues = group.rules.filter((r) => r.status === "fail" || r.status === "warn");
  const rest = group.rules.filter((r) => r.status === "pass" || r.status === "na");
  return (
    <li className={`cr-rule cr-rule--${group.status}`}>
      <button type="button" className="cr-rule__head" aria-expanded={open} onClick={onToggle}>
        <span className="cr-rule__no">{group.id}</span>
        <span className="cr-rule__text">
          <span className="cr-rule__title" title={group.description}>
            {group.title}
          </span>
          <span className="cr-rule__counts">
            {rawCounts(group.rules).map(([raw, n]) => (
              <span key={raw} className={`cr-count cr-count--${raw}`}>
                {n} {(rawStatusLabel[raw] ?? raw).toLowerCase()}
              </span>
            ))}
          </span>
        </span>
        <StatusIcon status={group.status} />
        <svg className="kb-icon cr-rule__chevron" viewBox="0 0 24 24" aria-hidden="true">
          <path d="m12 13.2 4.9-5 1.5 1.5-6.4 6.4-6.4-6.4 1.5-1.5 4.9 5Z" />
        </svg>
      </button>
      {open && (
        <div className="cr-rule__body">
          <ul className="cr-findings">
            {issues.map((r) => (
              <RuleRow key={r.id} rule={r} onOpen={onOpen} />
            ))}
            {rest.length > 0 && issues.length > 0 && !showRest ? (
              <li>
                <button type="button" className="cr-passed" onClick={() => setShowRest(true)}>
                  <StatusIcon status="pass" size={16} />
                  {rest.length} passed or not applicable
                </button>
              </li>
            ) : (
              rest.map((r) => <RuleRow key={r.id} rule={r} onOpen={onOpen} />)
            )}
          </ul>
        </div>
      )}
    </li>
  );
}

function Review({ view }: { view: CaseView }) {
  const { evaluation: ev } = view;
  const [focus, setFocus] = useState<Focus | null>(null);
  const previews = useDocumentPreviews(ev.case_id, view.docs);
  const [open, setOpen] = useState<Set<number>>(
    () => new Set(view.groups.filter((g) => g.status === "fail" || g.status === "warn").map((g) => g.id)),
  );
  const [searchParams, setSearchParams] = useSearchParams();
  const tab: Tab = searchParams.get("tab") === "activity" ? "activity" : "rules";
  const setTab = (next: Tab) =>
    setSearchParams(
      (prev) => {
        const params = new URLSearchParams(prev);
        if (next === "rules") params.delete("tab");
        else params.set("tab", next);
        return params;
      },
      { replace: true },
    );
  const evaluatedGroups = view.groups.filter((g) => g.evaluated);
  const duration = formatDuration(ev.started_at, ev.finished_at);

  const toggle = (id: number) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const jumpToRule = (ruleId: string) => {
    const group = view.groups.find((g) => g.rules.some((r) => r.id === ruleId));
    if (!group) return;
    setTab("rules");
    setOpen((prev) => new Set(prev).add(group.id));
    requestAnimationFrame(() => {
      const el = document.getElementById(`rule-${ruleId}`);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      el?.classList.add("is-flash");
      window.setTimeout(() => el?.classList.remove("is-flash"), 1200);
    });
    const source = view.rules.find((r) => r.id === ruleId)?.sources[0];
    if (source) setFocus({ docKey: source.docKey, page: source.page ?? 1, nonce: Date.now() });
  };

  return (
    <div className="cr">
      <header className="cr-header">
        <nav aria-label="Breadcrumb">
          <ol className="kb-breadcrumb cr-crumbs">
            <li>
              <Link to="/queue">Cases</Link>
            </li>
            <li aria-hidden="true">/</li>
            <li>{ev.case_id}</li>
          </ol>
        </nav>
        <div className="cr-header__row">
          <div>
            <h1 className="cr-title">
              {view.borrower ?? ev.case_id}{" "}
              {view.amount ? (
                <span className="cr-title__amount">{view.amount}</span>
              ) : (
                <span className="cr-title__amount cr-is-disabled" title="Loan amount isn't in the evaluation data">
                  Amount —
                </span>
              )}
            </h1>
            <p className="cr-header__meta">
              Case {ev.case_id} · Evaluation {ev.evaluation_id}
            </p>
          </div>
          <div className="cr-run">
            {ev.is_mock && <span className="cr-mock">Mock data</span>}
            <span className="kb-badge kb-badge--dark">
              {ev.status === "completed" ? (verdictLabel[ev.verdict ?? ""] ?? ev.verdict ?? "Completed") : ev.status}
            </span>
            <span>
              {formatTime(ev.started_at)}
              {duration && ` · ${duration}`}
            </span>
          </div>
        </div>
      </header>

      <section className={`cr-action cr-action--${view.decision ?? "none"}`} aria-labelledby="cr-action-title">
        <div className="cr-action__main">
          <div className="cr-action__head">
            <p className="cr-eyebrow">Agent recommendation</p>
            <h2 className="cr-action__title" id="cr-action-title">
              {view.headline}
            </h2>
            <div className="cr-action__summary">
              {view.fixes.length > 0 && (
                <span className="cr-raw cr-raw--fail">
                  {view.fixes.length} {view.fixes.length === 1 ? "rule needs" : "rules need"} attention
                </span>
              )}
              <span>
                {view.rules.length} of {ev.rules_total ?? view.rules.length} rules recorded
              </span>
              {ev.summary && ev.status !== "failed" && (
                <details className="cr-why">
                  <summary>Agent summary</summary>
                  <p>{ev.summary}</p>
                </details>
              )}
            </div>
          </div>
          {ev.status === "failed" && ev.summary && <p className="cr-failure">{ev.summary}</p>}
          {view.fixes.length > 0 ? (
            <ol className="cr-action__list">
              {view.fixes.map((f) => (
                <li key={f.ruleId} title={f.found ?? undefined}>
                  <span>{f.label}</span>
                  <span className="cr-action__refs">
                    <button type="button" className={`cr-ref cr-ref--${f.status}`} onClick={() => jumpToRule(f.ruleId)}>
                      {rawStatusLabel[view.rules.find((r) => r.id === f.ruleId)?.rawStatus ?? ""] ?? "Open"}
                    </button>
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="cr-muted">No rule needs correction.</p>
          )}
        </div>
        <aside className="cr-action__side">
          <div className="cr-score" aria-label="Checklist result">
            <div className="cr-score__bar">
              {view.groups.map((g) => (
                <span
                  key={g.id}
                  className={`cr-score__seg cr-score__seg--${g.evaluated ? g.status : "off"}`}
                  title={`${g.id}. ${g.title}${g.evaluated ? "" : " — not evaluated yet"}`}
                />
              ))}
            </div>
            <ul className="cr-score__legend">
              <li>
                <StatusIcon status="fail" size={16} /> {countRules(view.rules, "fail")} failed
              </li>
              <li>
                <StatusIcon status="warn" size={16} /> {countRules(view.rules, "warn")} to review
              </li>
              <li>
                <StatusIcon status="pass" size={16} /> {countRules(view.rules, "pass")} passed
              </li>
            </ul>
          </div>
          <p className="cr-confidence cr-is-disabled" title="The evaluator doesn't report confidence yet">
            Confidence <strong>—</strong>
          </p>
          <DecisionPanel key={ev.evaluation_id} view={view} />
        </aside>
      </section>

      <div className="cr-grid">
        <div className="cr-left">
          <dl className="cr-facts">
            {view.facts.map((f) => (
              <div key={f.label} className={f.value ? undefined : "cr-is-disabled"}>
                <dt>{f.label}</dt>
                <dd title={f.value ?? "Not in the evaluation data"}>{f.value ?? "—"}</dd>
              </div>
            ))}
          </dl>

          <section aria-label="Review details">
            <div className="cr-section-head">
              <div className="cr-tabs" role="tablist" aria-label="Review details">
                <button type="button" role="tab" aria-selected={tab === "rules"} className="cr-tab" onClick={() => setTab("rules")}>
                  Business rules <span className="cr-tab__count">{view.groups.length}</span>
                </button>
                <button type="button" role="tab" aria-selected={tab === "activity"} className="cr-tab" onClick={() => setTab("activity")}>
                  Agent activity <span className="cr-tab__count">{view.rules.length}</span>
                </button>
              </div>
              {tab === "rules" && (
                <button
                  type="button"
                  className="kb-link cr-expand"
                  onClick={() =>
                    setOpen((prev) => (prev.size === evaluatedGroups.length ? new Set() : new Set(evaluatedGroups.map((g) => g.id))))
                  }
                >
                  {open.size === evaluatedGroups.length ? "Collapse all" : "Expand all"}
                </button>
              )}
            </div>
            {tab === "rules" ? (
              <ol className="cr-rules">
                {view.groups.map((g) => (
                  <GroupCard key={g.id} group={g} open={open.has(g.id)} onToggle={() => toggle(g.id)} onOpen={setFocus} />
                ))}
              </ol>
            ) : (
              <div className="cr-panel">
                <ActivityTimeline view={view} onOpen={setFocus} />
              </div>
            )}
          </section>
        </div>

        <DocumentPanel
          caseId={ev.case_id}
          docs={previews.docs}
          missing={view.missingDocs}
          focus={focus}
          onSelect={setFocus}
          onPreviewError={previews.refresh}
        />
      </div>
    </div>
  );
}

function ReviewSkeleton() {
  return (
    <div className="cr" aria-busy="true" aria-label="Loading evaluation">
      <header className="cr-header">
        <div className="cr-header__row">
          <div className="bo-skeleton-stack">
            <Skeleton width="8rem" height="0.875rem" />
            <Skeleton width="22rem" height="2.25rem" />
            <Skeleton width="18rem" />
          </div>
          <Skeleton width="16rem" height="3rem" />
        </div>
      </header>

      <section className="cr-action cr-action--none">
        <div className="bo-skeleton-stack">
          <Skeleton width="9rem" height="0.75rem" />
          <Skeleton width="60%" height="1.75rem" />
          <Skeleton width="40%" />
          <Skeleton width="80%" />
          <Skeleton width="70%" />
        </div>
        <div className="cr-action__side">
          <Skeleton height="0.5rem" />
          <Skeleton width="70%" />
          <Skeleton height="2.5rem" />
        </div>
      </section>

      <div className="cr-grid">
        <div className="cr-left">
          <div className="cr-facts">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="bo-skeleton-stack">
                <Skeleton width="5rem" height="0.75rem" />
                <Skeleton width="8rem" />
              </div>
            ))}
          </div>
          <ol className="cr-rules">
            {Array.from({ length: 6 }, (_, i) => (
              <li key={i} className="cr-rule cr-rule--skeleton">
                <div className="cr-rule__head">
                  <Skeleton width="2rem" height="2rem" className="bo-skeleton--pill" />
                  <Skeleton width="60%" />
                  <Skeleton width="4rem" height="1.25rem" className="bo-skeleton--pill" />
                </div>
              </li>
            ))}
          </ol>
        </div>
        <div className="cr-docs">
          <div className="cr-docs__strip">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} width="4rem" height="5rem" />
            ))}
          </div>
          <div className="cr-docs__pages">
            <div className="cr-page" style={{ height: "40rem" }} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CaseReviewPage() {
  const caseId = useParams<{ caseId: string }>().caseId ?? null;
  const evaluationId = useSearchParams()[0].get("evaluation");
  const state = useEvaluation({ caseId, evaluationId });

  const view = useMemo(
    () =>
      state.status === "ready" && state.payload.evaluation
        ? createCaseView(state.payload.evaluation, state.payload.results)
        : null,
    [state],
  );

  if (state.status === "loading") return <ReviewSkeleton />;
  if (state.status === "error") return <p className="cr-state cr-state--error">Couldn't load the evaluation: {state.message}</p>;
  if (!view) {
    const missing = evaluationId ? `Evaluation ${evaluationId} not found.` : caseId ? `Case ${caseId} has no evaluation yet.` : "No evaluation yet.";
    return <p className="cr-state">{missing}</p>;
  }
  // "/cases" shows the latest run; give it its case's address so the link can be shared.
  if (!caseId) return <Navigate to={getCasePath(view.evaluation.case_id)} replace />;

  return <Review key={view.evaluation.evaluation_id} view={view} />;
}
