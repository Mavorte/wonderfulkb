import type { CheckStatus } from "./evaluation";

const paths: Record<CheckStatus, string> = {
  pass: "M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm4.3 6.3-5.8 5.8-2.8-2.8-1.4 1.4 4.2 4.2 7.2-7.2-1.4-1.4Z",
  fail: "M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm3.5 5.1L12 10.6 8.5 7.1 7.1 8.5l3.5 3.5-3.5 3.5 1.4 1.4 3.5-3.5 3.5 3.5 1.4-1.4-3.5-3.5 3.5-3.5-1.4-1.4Z",
  warn: "M12 2.5 22.5 21h-21L12 2.5ZM11 9v6h2V9h-2Zm0 8v2h2v-2h-2Z",
  na: "M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm0 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16Zm-5 7h10v2H7v-2Z",
};

export const statusLabel: Record<CheckStatus, string> = {
  pass: "Passed",
  fail: "Failed",
  warn: "Needs review",
  na: "Not applicable",
};

export default function StatusIcon({ status, size = 24 }: { status: CheckStatus; size?: 16 | 24 }) {
  return (
    <svg
      className={`kb-icon cr-status-icon cr-status-icon--${status}${size === 16 ? " kb-icon--16" : ""}`}
      viewBox="0 0 24 24"
      role="img"
      aria-label={statusLabel[status]}
    >
      <path d={paths[status]} />
    </svg>
  );
}
