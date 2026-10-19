import { useState, type ReactNode } from "react";
import KbLogo from "./kb/kb-logo.svg?react";
import CasesPage from "./cases/CasesPage";
import NewCasePage from "./cases/NewCasePage";
import ClientsPage from "./clients/ClientsPage";
import QueuePage from "./queue/QueuePage";

type Page = "queue" | "cases" | "new-case" | "clients";

const navItems: { page: Page; label: string; icon: ReactNode }[] = [
  {
    page: "queue",
    label: "Work queue",
    icon: <path d="M3 5h4v4H3V5Zm6 1h12v2H9V6Zm-6 5h4v4H3v-4Zm6 1h12v2H9v-2Zm-6 5h4v4H3v-4Zm6 1h12v2H9v-2Z" />,
  },
  {
    page: "cases",
    label: "All cases",
    icon: <path d="M4 5h16v2H4V5Zm0 6h16v2H4v-2Zm0 6h16v2H4v-2Z" />,
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
                  onClick={() => setPage(item.page)}
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
        {page === "queue" && <QueuePage />}
        {page === "cases" && <CasesPage onNewCase={() => setPage("new-case")} />}
        {page === "new-case" && <NewCasePage />}
        {page === "clients" && <ClientsPage />}
      </main>
    </div>
  );
}
