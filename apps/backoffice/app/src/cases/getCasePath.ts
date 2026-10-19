/** The app route of a case's review; without an evaluation it shows the case's latest run. */
export default function getCasePath(caseId: string, evaluationId?: string) {
  const path = `/cases/${encodeURIComponent(caseId)}`;
  return evaluationId ? `${path}?evaluation=${encodeURIComponent(evaluationId)}` : path;
}
