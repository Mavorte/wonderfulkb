import { toneOf, type Mark, type SourceRef } from "./evaluation.ts";

export interface Focus {
  docKey: string;
  page: number;
  // The rule whose places are shown; its evidence boxes are drawn only while it is selected.
  ruleId?: string;
  // The place to scroll to and highlight.
  source?: SourceRef;
  // Changes on every click so re-selecting the same page scrolls again.
  nonce: number;
}

export function focusOn(source: SourceRef): Focus {
  return { docKey: source.docKey, page: source.page ?? 1, ruleId: source.ruleId, source, nonce: Date.now() };
}

// Problems of rules that didn't pass are always drawn; everything else only for the selected rule.
function markLabel(m: Mark) {
  const what = m.source.issue ?? m.source.field?.replace(/_/g, " ");
  return [m.ruleLabel, what, m.source.quote && `“${m.source.quote}”`].filter(Boolean).join(" · ");
}

// One box per spot: the highlighted place, then problems, win over evidence on the same bbox;
// the label lists every place drawn there.
export function visibleMarks(marks: Mark[], page: number, focus: Focus | null): { mark: Mark; label: string }[] {
  const rank = (m: Mark) => (m.source.id === focus?.source?.id ? 0 : m.source.problem ? 1 : 2);
  const byBox = new Map<string, { mark: Mark; labels: string[] }>();
  for (const m of marks) {
    if (m.source.page !== page) continue;
    if (toneOf(m.source, m.status) === "evidence" && m.ruleId !== focus?.ruleId) continue;
    const key = m.source.bbox!.join(",");
    const spot = byBox.get(key) ?? { mark: m, labels: [] };
    if (rank(m) < rank(spot.mark)) spot.mark = m;
    const label = markLabel(m);
    if (!spot.labels.includes(label)) spot.labels.push(label);
    byBox.set(key, spot);
  }
  return [...byBox.values()].map(({ mark, labels }) => ({ mark, label: labels.join("\n") }));
}
