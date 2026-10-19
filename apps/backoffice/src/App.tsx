import logo from "../../../design-system/assets/kb-logo.svg";
import { NewCasePage } from "./cases/NewCasePage";

export function App() {
  return (
    <div className="kb-root bo-shell">
      <aside className="bo-sidebar">
        <div className="bo-brand">
          <img src={logo} alt="Komerční banka" height={32} />
          <span className="bo-brand__name">Backoffice</span>
        </div>
        <nav aria-label="Main">
          <ul className="bo-nav">
            <li>
              <a className="bo-nav__item" href="#/cases/new" aria-current="page">
                <svg className="kb-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z" />
                </svg>
                New case
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
