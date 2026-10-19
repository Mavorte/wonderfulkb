import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes, matchPath, useLocation } from "react-router-dom";
import KbLogo from "./kb/kb-logo.svg?react";
import NewCasePage from "./cases/NewCasePage";
import ClientsPage from "./clients/ClientsPage";
import QueuePage from "./queue/QueuePage";
import CaseReviewPage from "./review/CaseReviewPage";

// Routes are relative to the app; the host mounts them under /apps/<slug>.
const navItems: { to: string; label: string; matches: string[]; icon: ReactNode }[] = [
  {
    to: "/cases/new",
    label: "New case",
    matches: ["/cases/new"],
    icon: <path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z" />,
  },
  {
    to: "/queue",
    label: "Work queue",
    matches: ["/queue", "/cases", "/cases/:caseId"],
    icon: <path d="M3 5h4v4H3V5Zm6 1h12v2H9V6Zm-6 5h4v4H3v-4Zm6 1h12v2H9v-2Zm-6 5h4v4H3v-4Zm6 1h12v2H9v-2Z" />,
  },
  {
    to: "/clients",
    label: "Clients",
    matches: ["/clients", "/clients/:clientId"],
    icon: <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm0 2c-4 0-8 2-8 5v1h16v-1c0-3-4-5-8-5Z" />,
  },
];

// Built with the Komerční banka design system (src/kb) instead of
// @wonderful/ui-base, so the app matches KB's own visual language.
export default function App() {
  const { pathname } = useLocation();
  // "/cases/new" also matches "/cases/:caseId", so "New case" must stay before "Work queue".
  const current = navItems.find((item) => item.matches.some((pattern) => matchPath(pattern, pathname)));

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
              <li key={item.to}>
                <Link className="bo-nav__item" to={item.to} aria-current={item === current ? "page" : undefined}>
                  <svg className="kb-icon" viewBox="0 0 24 24" aria-hidden="true">
                    {item.icon}
                  </svg>
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <main className="bo-main">
        <Routes>
          <Route path="/queue" element={<QueuePage />} />
          <Route path="/cases" element={<CaseReviewPage />} />
          <Route path="/cases/new" element={<NewCasePage />} />
          <Route path="/cases/:caseId" element={<CaseReviewPage />} />
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/clients/:clientId" element={<ClientsPage />} />
          <Route path="*" element={<Navigate to="/queue" replace />} />
        </Routes>
      </main>
    </div>
  );
}
