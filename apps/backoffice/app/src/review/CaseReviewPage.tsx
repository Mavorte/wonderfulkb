import { useMemo, useState } from "react";
import Skeleton from "../Skeleton";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import ActivityTimeline from "./ActivityTimeline";
import DecisionPanel from "./DecisionPanel";
import DocumentPanel from "./DocumentPanel";
import { focusOn, type Focus } from "./focus";
import EvidenceChip from "./EvidenceChip";
import StatusIcon from "./StatusIcon";
import {
  createCaseView,
  focusSourceOf,
  groupSources,
  problemsOf,
  shortTitle,
  toneOf,
  formatDuration,
  formatTime,
  isRunning,
  type CaseView,
  type CheckStatus,
  type Problem,
  type RuleGroup,
  type RuleView,
  type SourceRef,
} from "./evaluation";
import { rawStatusLabel } from "./ruleLabels";
import formatDate from "../cases/formatDate";
import getCasePath from "../cases/getCasePath";
import useQueueContext from "../queue/useQueueContext";
import useDocumentPreviews from "./useDocumentPreviews";
import useEvaluation from "./useEvaluation";

type Tab = "rules" | "activity";

const verdictLabel: Record<string, string> = {
  needs_correction: "Needs correction",
  ready: "Ready",
  approved: "Ready",
  rejected: "Rejected",
};

// Generated case ids are UUIDs; show a readable prefix and keep the full id in the tooltip.
function shortId(id: string) {
  return id.length > 12 ? id.slice(0, 8) : id;
}

function countRules(rules: RuleView[], status: CheckStatus) {
  return rules.filter((r) => r.status === status).length;
}

function rawCounts(rules: RuleView[]) {
  const counts = new Map<string, number>();
  for (const r of rules) counts.set(r.rawStatus, (counts.get(r.rawStatus) ?? 0) + 1);
  return [...counts.entries()];
}

function Place({ source, tone, onOpen }: { source: SourceRef; tone: string; onOpen: (focus: Focus) => void }) {
  const where = `${shortTitle(source.title)}${source.page ? ` · p. ${source.page}` : ""}`;
  return (
    <button
      type="button"
      className={`cr-place cr-place--${tone}`}
      title={[`${source.title}${source.page ? `, page ${source.page}` : ""}`, source.quote].filter(Boolean).join(": ")}
      onClick={() => onOpen(focusOn(source))}
    >
      {source.quote && <span className="cr-place__quote">{source.quote}</span>}
      <span className="cr-place__src">{where}</span>
    </button>
  );
}

function problemTitle(p: Problem) {
  const label = p.label.replace(/_/g, " ");
  if (p.kind === "compare") return `${label} differs`;
  if (p.kind === "missing_value") return `${label} missing`;
  if (p.kind === "declaration") return `Requires ${label}`;
  return label;
}

function ProblemList({ rule, onOpen }: { rule: RuleView; onOpen: (focus: Focus) => void }) {
  const problems = problemsOf(rule);
  if (!problems.length) return null;
  return (
    <ul className="cr-problems">
      {problems.map((p) => (
        <li key={p.key} className="cr-problem">
          <span className="cr-problem__title">{problemTitle(p)}</span>
          <span className="cr-problem__places">
            {p.sides.map((side, i) => (
              <span key={side.side} className="cr-problem__side">
                {i > 0 && <span className="cr-problem__ne" aria-label="differs from">≠</span>}
                {side.side && <span className="cr-problem__letter">{side.side.toUpperCase()}</span>}
                {side.sources.map((src) => (
                  <Place key={src.id} source={src} tone={toneOf(src, rule.status)} onOpen={onOpen} />
                ))}
              </span>
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}

function RuleRow({ rule, selected, onOpen }: { rule: RuleView; selected: boolean; onOpen: (focus: Focus) => void }) {
  return (
    <li className={`cr-finding cr-finding--${rule.status}${selected ? " is-selected" : ""}`} id={`rule-${rule.id}`}>
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
        <ProblemList rule={rule} onOpen={onOpen} />
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
  running,
  selectedRuleId,
  showRest,
  onShowRest,
}: {
  running: boolean;
  selectedRuleId: string | undefined;
  showRest: boolean;
  onShowRest: () => void;
  group: RuleGroup;
  open: boolean;
  onToggle: () => void;
  onOpen: (focus: Focus) => void;
}) {
  if (!group.evaluated) {
    return (
      <li className="cr-rule cr-rule--disabled" aria-disabled="true">
        <div className="cr-rule__head">
          <span className="cr-rule__no">{group.id}</span>
          <span className="cr-rule__text">
            <span className="cr-rule__title" title={group.description}>
              {group.title}
            </span>
            <span className="cr-rule__counts">{running ? "Waiting for the agent…" : "Not evaluated by the agent yet"}</span>
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
              <RuleRow key={r.id} rule={r} selected={r.id === selectedRuleId} onOpen={onOpen} />
            ))}
            {rest.length > 0 && issues.length > 0 && !showRest ? (
              <li>
                <button type="button" className="cr-passed" onClick={onShowRest}>
                  <StatusIcon status="pass" size={16} />
                  {rest.length} passed or not applicable
                </button>
              </li>
            ) : (
              rest.map((r) => <RuleRow key={r.id} rule={r} selected={r.id === selectedRuleId} onOpen={onOpen} />)
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
  // Groups whose passed and not-applicable rules are unfolded.
  const [showRest, setShowRest] = useState<Set<number>>(() => new Set());
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
  const queued = useQueueContext().queue?.find((c) => c.case_id === ev.case_id);
  const evaluatedGroups = view.groups.filter((g) => g.evaluated);
  const duration = formatDuration(ev.started_at, ev.finished_at);
  const running = isRunning(ev);
  const total = ev.rules_total ?? view.rules.length;
  const progress = total ? Math.round((view.rules.length / total) * 100) : 0;

  const toggle = (id: number) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  // Opens the rule in the list and shows `source` (default: its first problem place) in the viewer.
  const jumpToRule = (ruleId: string, source?: SourceRef) => {
    const group = view.groups.find((g) => g.rules.some((r) => r.id === ruleId));
    if (!group) return;
    const rule = group.rules.find((r) => r.id === ruleId)!;
    setTab("rules");
    setOpen((prev) => new Set(prev).add(group.id));
    // The passed and not-applicable rules are folded away until shown.
    if (rule.status === "pass" || rule.status === "na") setShowRest((prev) => new Set(prev).add(group.id));
    requestAnimationFrame(() => {
      const el = document.getElementById(`rule-${ruleId}`);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      el?.classList.add("is-flash");
      window.setTimeout(() => el?.classList.remove("is-flash"), 1200);
    });
    const target = source ?? focusSourceOf(rule);
    if (target) setFocus(focusOn(target));
  };

  const title = queued?.client?.name ?? view.borrower ?? `Case ${shortId(ev.case_id)}`;
  const ico = queued?.client?.ico ?? view.ico;
  const meta = [
    ico && `IČO ${ico}`,
    view.loanNo && `Loan contract ${view.loanNo}`,
    queued?.created_at && `opened ${formatDate(queued.created_at)}`,
  ].filter(Boolean);

  return (
    <div className="cr">
      <header className="cr-header">
        <nav aria-label="Breadcrumb">
          <ol className="kb-breadcrumb cr-crumbs">
            <li>
              <Link to="/queue">Work queue</Link>
            </li>
            <li aria-hidden="true">/</li>
            <li aria-current="page">{title}</li>
          </ol>
        </nav>
        <div className="cr-header__row">
          <div>
            <h1 className="cr-title" title={`Case ${ev.case_id}`}>
              {title}
            </h1>
            {meta.length > 0 && <p className="cr-header__meta">{meta.join(" · ")}</p>}
          </div>
          <div className="cr-run" title={`Evaluation ${ev.evaluation_id}`}>
            {ev.is_mock && <span className="cr-mock">Mock data</span>}
            {running ? (
              <span className="cr-live">Agent evaluating</span>
            ) : (
              <span className="kb-badge kb-badge--dark">
                {ev.status === "completed" ? (verdictLabel[ev.verdict ?? ""] ?? ev.verdict ?? "Completed") : ev.status}
              </span>
            )}
            <span>
              {running ? "Started" : "Checked"} {formatTime(ev.started_at)}
              {duration && `${running ? " ·" : " in"} ${duration}`}
            </span>
          </div>
        </div>
      </header>

      <section className={`cr-action cr-action--${running ? "running" : (view.decision ?? "none")}`} aria-labelledby="cr-action-title">
        {running ? (
          <div className="cr-action__main" aria-live="polite">
            <p className="cr-eyebrow">Agent at work</p>
            <h2 className="cr-action__title" id="cr-action-title">
              {view.headline}
            </h2>
            <div
              className="cr-progress"
              role="progressbar"
              aria-label="Rules checked"
              aria-valuemin={0}
              aria-valuemax={total}
              aria-valuenow={view.rules.length}
            >
              <span className="cr-progress__fill" style={{ width: `${Math.max(progress, 2)}%` }} />
            </div>
            <p className="cr-progress__label">
              <strong>
                {view.rules.length} of {total}
              </strong>{" "}
              rules checked · this page updates on its own
            </p>
            {view.fixes.length > 0 ? (
              <>
                <p className="cr-progress__found">Found so far</p>
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
              </>
            ) : (
              <p className="cr-muted">{view.rules.length ? "No issues found so far." : "The agent is opening the case documents."}</p>
            )}
          </div>
        ) : (
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
        )}
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
            {view.rules.length > 0 && (
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
            )}
          </div>
          {running ? (
            <div className="cr-locked">
              <p className="cr-locked__title">Your decision</p>
              <p className="cr-muted">You can decide once the agent finishes all {total} rules.</p>
            </div>
          ) : (
            <>
              <p className="cr-confidence cr-is-disabled" title="The evaluator doesn't report confidence yet">
                Confidence <strong>—</strong>
              </p>
              <DecisionPanel key={ev.evaluation_id} view={view} />
            </>
          )}
        </aside>
      </section>

      <div className="cr-grid">
        <div className="cr-left">
          <dl className="cr-facts">
            {view.facts.map((f) => (
              <div key={f.label} className={f.value || running ? undefined : "cr-is-disabled"}>
                <dt>{f.label}</dt>
                <dd title={f.value ?? (running ? "Not extracted yet" : "Not in the evaluation data")}>
                  {f.value ?? (running ? <Skeleton width="6rem" /> : "—")}
                </dd>
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
              {tab === "rules" && evaluatedGroups.length > 0 && (
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
                  <GroupCard
                    key={g.id}
                    running={running}
                    group={g}
                    open={open.has(g.id)}
                    onToggle={() => toggle(g.id)}
                    onOpen={setFocus}
                    selectedRuleId={focus?.ruleId}
                    showRest={showRest.has(g.id)}
                    onShowRest={() => setShowRest((prev) => new Set(prev).add(g.id))}
                  />
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
          running={running}
          caseId={ev.case_id}
          docs={previews.docs}
          missing={view.missingDocs}
          focus={focus}
          onSelect={setFocus}
          onOpenMark={(mark) => jumpToRule(mark.ruleId, mark.source)}
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
