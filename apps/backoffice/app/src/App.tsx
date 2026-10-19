import { useState, type ReactNode } from "react";
import KbLogo from "./kb/kb-logo.svg?react";
import CasesPage from "./cases/CasesPage";
import NewCasePage from "./cases/NewCasePage";

type Page = "cases" | "new-case";

const navItems: { page: Page; label: string; icon: ReactNode }[] = [
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
];

// Built with the Komerční banka design system (src/kb) instead of
// @wonderful/ui-base, so the app matches KB's own visual language.
export default function App() {
  const [page, setPage] = useState<Page>("cases");

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
        {page === "cases" ? <CasesPage onNewCase={() => setPage("new-case")} /> : <NewCasePage />}
      </main>
    </div>
  );
}
