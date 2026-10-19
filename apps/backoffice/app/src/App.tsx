import { useState, type ReactNode } from "react";
import KbLogo from "./kb/kb-logo.svg?react";
import NewCasePage from "./cases/NewCasePage";
import ClientsPage from "./clients/ClientsPage";
import QueuePage from "./queue/QueuePage";
import CaseReviewPage from "./review/CaseReviewPage";

type Page = "queue" | "case-review" | "new-case" | "clients";

const navItems: { page: Page; label: string; icon: ReactNode }[] = [
  {
    page: "queue",
    label: "Work queue",
    icon: <path d="M3 5h4v4H3V5Zm6 1h12v2H9V6Zm-6 5h4v4H3v-4Zm6 1h12v2H9v-2Zm-6 5h4v4H3v-4Zm6 1h12v2H9v-2Z" />,
  },
  {
    page: "case-review",
    label: "Case review",
    icon: (
      <path d="M9 2h6v2h4a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h4V2Zm0 4H6v14h12V6h-3v2H9V6Zm1.5 10.4-3-3 1.4-1.4 1.6 1.6 4.6-4.6 1.4 1.4-6 6Z" />
    ),
  },
  {
    page: "new-case",
    label: "New case",
    icon: <path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z" />,
  },
  {
    page: "clients",
    label: "Clients",
    icon: <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-4 0-8 2-8 5v1h16v-1c0-3-4-5-8-5Z" />,
  },
];

// Built with the Komerční banka design system (src/kb) instead of
// @wonderful/ui-base, so the app matches KB's own visual language.
export default function App() {
  const [page, setPage] = useState<Page>("queue");
  const [reviewId, setReviewId] = useState<string | null>(null);

  const openReview = (evaluationId: string) => {
    setReviewId(evaluationId);
    setPage("case-review");
  };

  return (
    <div className="app-root bo-shell">
      <aside className="bo-sidebar">
        <div className="bo-brand">
          <KbLogo role="img" aria-label="Komerční banka" height={32} width={97} />
          <span className="bo-brand__name">Backoffice</span>
        </div>
        <nav aria-label="Main">
          <ul className="bo-nav">
            {navItems.map((item) => (
              <li key={item.page}>
                <button
                  type="button"
                  className="bo-nav__item"
                  aria-current={page === item.page ? "page" : undefined}
                  onClick={() => {
                    // The nav item opens the review from the URL, not the last case opened from the queue.
                    if (item.page === "case-review") setReviewId(null);
                    setPage(item.page);
                  }}
                >
                  <svg className="kb-icon" viewBox="0 0 24 24" aria-hidden="true">
                    {item.icon}
                  </svg>
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <main className="bo-main">
        {page === "queue" && <QueuePage onOpenReview={openReview} />}
        {page === "case-review" && <CaseReviewPage key={reviewId} initialEvaluationId={reviewId} />}
        {page === "new-case" && <NewCasePage />}
        {page === "clients" && <ClientsPage />}
      </main>
    </div>
  );
}
