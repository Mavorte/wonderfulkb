import KbLogo from "./kb/kb-logo.svg?react";
import NewCasePage from "./cases/NewCasePage";
import "./kb/tokens.css";
import "./kb/components.css";
import "./style.css";

// Built with the Komerční banka design system (src/kb) instead of
// @wonderful/ui-base, so the app matches KB's own visual language.
export default function App() {
  return (
    <div className="app-root bo-shell">
      <aside className="bo-sidebar">
        <div className="bo-brand">
          <KbLogo role="img" aria-label="Komerční banka" height={32} width={97} />
          <span className="bo-brand__name">Backoffice</span>
        </div>
        <nav aria-label="Main">
          <ul className="bo-nav">
            <li>
              <a className="bo-nav__item" href="#new-case" aria-current="page">
                <svg className="kb-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z" />
                </svg>
                Úvěrové případy
              </a>
            </li>
          </ul>
        </nav>
      </aside>
      <main className="bo-main">
        <NewCasePage />
      </main>
    </div>
  );
}
