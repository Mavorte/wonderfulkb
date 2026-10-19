import "./style.css";
import { useWonderful } from "@wonderful/app-sdk";
import { useEffect, useRef, useState } from "react";
import CaseSummary from "./components/CaseSummary";
import Notice from "./components/Notice";
import UploadPanel from "./components/UploadPanel";
import getIntakeHash from "./getIntakeHash";
import KbLogo from "./kb/kb-logo.svg?react";
import KbLogoInverse from "./kb/kb-logo-inverse.svg?react";
import type { IntakeData } from "./types";

type State =
  | { status: "loading" }
  | { status: "error"; title: string; description: string }
  | { status: "ready"; data: IntakeData };

const INVALID_LINK = {
  title: "This link is not valid",
  description: "Please use the link from your latest message, or contact your KB advisor for a new one.",
};

function getErrorState(error: unknown): State {
  const message = error instanceof Error ? error.message : String(error);
  if (/401|expired/i.test(message)) {
    return {
      status: "error",
      title: "This link has expired",
      description: "Please contact your KB advisor and ask for a new link.",
    };
  }
  if (/404|invalid_link|case_not_found/i.test(message)) return { status: "error", ...INVALID_LINK };
  return {
    status: "error",
    title: "Something went wrong",
    description: "We could not load your case. Please try again in a few minutes.",
  };
}

export default function App() {
  const { api, track } = useWonderful();
  const [state, setState] = useState<State>({ status: "loading" });
  const hasTrackedOpen = useRef(false);

  useEffect(() => {
    if (!hasTrackedOpen.current) {
      hasTrackedOpen.current = true;
      track("intake_opened");
    }
    const hash = getIntakeHash();
    if (!hash) {
      setState({ status: "error", ...INVALID_LINK });
      return;
    }
    api
      .invokeFunction<IntakeData & { error?: string }>("client-intake/intake-get", {
        method: "POST",
        params: { hash },
      })
      .then((result) => {
        if (result?.error) setState(getErrorState(result.error));
        else setState({ status: "ready", data: result });
      })
      .catch((error) => setState(getErrorState(error)));
    // Load once per page open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="kb-root app-root">
      <header className="app-header">
        <div className="app-container">
          <KbLogo className="app-header__logo" />
          <span className="app-header__tag">Equipment financing</span>
        </div>
      </header>
      <main className="app-main">
        <div className="app-container">
          <div className="app-intro">
            <h1>Documents for your financing</h1>
            <p>Check your case details and upload the requested documents as PDF files.</p>
          </div>
          {state.status === "loading" && (
            <div className="app-loader" role="status">
              <div className="app-loader__spinner" />
              <p>Loading your case</p>
            </div>
          )}
          {state.status === "error" && <Notice variant="error" title={state.title} description={state.description} />}
          {state.status === "ready" && (
            <div className="app-stack">
              <CaseSummary data={state.data} />
              <UploadPanel data={state.data} />
            </div>
          )}
        </div>
      </main>
      <footer className="app-footer">
        <div className="app-container">
          <KbLogoInverse className="app-footer__logo" />
          <span>© Komerční banka, a.s.</span>
        </div>
      </footer>
    </div>
  );
}
