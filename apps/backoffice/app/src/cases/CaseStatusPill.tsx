import { caseStatusLabel, isCaseStatus } from "./caseStatus";
import "./caseStatus.css";

/** Shows a case status by its label; a status outside the lifecycle shows as sent. */
export default function CaseStatusPill({ status }: { status: string }) {
  return (
    <span className={`bo-status bo-status--${status}`}>{isCaseStatus(status) ? caseStatusLabel[status] : status}</span>
  );
}
