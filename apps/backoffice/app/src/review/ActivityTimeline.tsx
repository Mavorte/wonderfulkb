import type { Focus } from "./DocumentPanel";
import EvidenceChip from "./EvidenceChip";
import StatusIcon from "./StatusIcon";
import { groupSources, type CaseView, type CheckStatus, type SourceRef } from "./evaluation";
import { rawStatusLabel } from "./ruleLabels";

interface Event {
  at: string;
  title: string;
  detail?: string;
  status?: CheckStatus;
  sources?: SourceRef[];
}

function time(iso: string) {
  return new Date(iso).toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Built from the run's start/finish and the moment each rule result was recorded.
function eventsFor(view: CaseView): Event[] {
  const { evaluation, rules } = view;
  const events: Event[] = [];
  if (evaluation.started_at) events.push({ at: evaluation.started_at, title: "Evaluation started", detail: `Case ${evaluation.case_id}` });
  for (const rule of [...rules].filter((r) => r.recordedAt).sort((a, b) => a.recordedAt!.localeCompare(b.recordedAt!))) {
    events.push({
      at: rule.recordedAt!,
      title: `${rule.label} — ${rawStatusLabel[rule.rawStatus] ?? rule.rawStatus}`,
      detail: rule.found ?? undefined,
      status: rule.status,
      sources: rule.sources,
    });
  }
  if (evaluation.finished_at) {
    events.push({
      at: evaluation.finished_at,
      title: evaluation.status === "failed" ? "Evaluation failed" : "Evaluation finished",
      detail: `${rules.length} of ${evaluation.rules_total ?? rules.length} rules recorded`,
      status: evaluation.status === "failed" ? "fail" : undefined,
    });
  }
  return events;
}

export default function ActivityTimeline({ view, onOpen }: { view: CaseView; onOpen: (focus: Focus) => void }) {
  return (
    <ol className="cr-timeline">
      {eventsFor(view).map((event, i) => (
        <li key={`${event.at}-${i}`} className="cr-event">
          <span className="cr-event__dot">
            {event.status ? <StatusIcon status={event.status} size={16} /> : <span className="cr-event__pip" />}
          </span>
          <div className="cr-event__body">
            <p className="cr-event__head">
              <span className="cr-event__title">{event.title}</span>
              <time className="cr-event__time" dateTime={event.at}>
                {time(event.at)}
              </time>
            </p>
            {event.detail && <p className="cr-event__detail">{event.detail}</p>}
            {!!event.sources?.length && (
              <div className="cr-finding__evidence">
                {groupSources(event.sources).map((s) => (
                  <EvidenceChip key={s.docKey} source={s} onOpen={onOpen} />
                ))}
              </div>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
