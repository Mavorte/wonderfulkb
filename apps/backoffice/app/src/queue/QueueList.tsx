import { useState } from "react";
import { Link } from "react-router-dom";
import Skeleton from "../Skeleton";
import CaseStatusPill from "../cases/CaseStatusPill";
import formatDate from "../cases/formatDate";
import getCasePath from "../cases/getCasePath";
import tierTitle from "./tierTitle";
import { tiers, type TriagedCase } from "./triage";
import type { QueueState } from "./useQueue";

const matches = (c: TriagedCase, query: string) =>
  [c.client?.name, c.client?.ico, c.case_id].some((value) => value?.toLowerCase().includes(query));

function QueueItem({ c, selected }: { c: TriagedCase; selected: boolean }) {
  const [top, ...rest] = c.findings;
  return (
    <li>
      <Link className="bo-qlist__item" to={getCasePath(c.case_id)} aria-current={selected ? "page" : undefined}>
        <span className="bo-qlist__head">
          <span className="bo-qlist__name">{c.client?.name ?? "Unknown client"}</span>
          <CaseStatusPill status={c.status} />
        </span>
        <span className="bo-qlist__meta">
          {[c.client ? `IČO ${c.client.ico}` : c.case_id, c.created_at && `opened ${formatDate(c.created_at)}`]
            .filter(Boolean)
            .join(" · ")}
        </span>
        {top && (
          <span className="bo-qlist__finding">
            <span className={`bo-queue__severity bo-queue__severity--${top.severity}`}>
              {top.severity === "blocking" ? "Blocking" : "Material"}
            </span>
            {top.title}
            {rest.length > 0 && <span className="bo-qlist__more"> +{rest.length} more</span>}
          </span>
        )}
      </Link>
    </li>
  );
}

function QueueListSkeleton() {
  return (
    <ul className="bo-qlist__items" aria-busy="true" aria-label="Loading cases">
      {[0, 1, 2, 3, 4].map((i) => (
        <li key={i} className="bo-qlist__item bo-skeleton-stack">
          <Skeleton width="70%" />
          <Skeleton width="50%" height="0.875rem" />
          <Skeleton width="85%" height="0.875rem" />
        </li>
      ))}
    </ul>
  );
}

export default function QueueList({
  state,
  queue,
  selectedId,
}: {
  state: QueueState;
  queue: TriagedCase[] | undefined;
  selectedId: string | undefined;
}) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const shown = queue?.filter((c) => !q || matches(c, q));

  return (
    <aside className="bo-qlist" aria-label="Work queue">
      <div className="bo-qlist__top">
        <div className="bo-qlist__title-row">
          <h1 className="bo-qlist__title">Work queue</h1>
          <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={state.load}>
            Refresh
          </button>
        </div>
        <input
          type="search"
          className="kb-input bo-qlist__search"
          placeholder="Search client, IČO or case"
          aria-label="Search cases"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="bo-qlist__scroll">
        {state.error ? (
          <div className="bo-empty bo-qlist__empty" role="alert">
            <p>The work queue could not be loaded.</p>
            <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={state.load}>
              Try again
            </button>
          </div>
        ) : !shown ? (
          <QueueListSkeleton />
        ) : shown.length === 0 ? (
          <p className="bo-empty bo-qlist__empty">{q ? "No case matches the search." : "The queue is empty."}</p>
        ) : (
          tiers.map((tier) => {
            const cases = shown.filter((c) => c.tier === tier);
            if (cases.length === 0) return null;
            return (
              <section key={tier} className="bo-qlist__group" aria-labelledby={`qlist-${tier}`}>
                <h2 id={`qlist-${tier}`} className="bo-qlist__group-title">
                  <span className={`bo-queue__dot bo-queue__dot--${tier}`} aria-hidden="true" />
                  {tierTitle[tier]}
                  <span className="bo-queue__section-count">{cases.length}</span>
                </h2>
                <ul className="bo-qlist__items">
                  {cases.map((c) => (
                    <QueueItem key={c.case_id} c={c} selected={c.case_id === selectedId} />
                  ))}
                </ul>
              </section>
            );
          })
        )}
        {state.payload?.truncated && <p className="bo-qlist__note">The list was cut short, so not every case is shown.</p>}
      </div>
    </aside>
  );
}
