import "./style.css";
import { useWonderful } from "@wonderful/app-sdk";
import { useEffect, useRef, useState } from "react";
import CaseCard from "./components/CaseCard";
import ChatPanel from "./components/ChatPanel";
import Notice from "./components/Notice";
import getIntakeHash from "./getIntakeHash";
import KbLogo from "./kb/kb-logo.svg?react";
import KbLogoInverse from "./kb/kb-logo-inverse.svg?react";
import type { ChatPageData } from "./types";

type State =
  | { status: "loading" }
  | { status: "error"; title: string; description: string }
  | { status: "ready"; data: ChatPageData };

const INVALID_LINK = {
  title: "This link is not valid",
  description: "Please use the link from your latest message, or contact your KB advisor for a new one.",
};

function getErrorState(error: unknown): State {
  const message = error instanceof Error ? error.message : String(error);
  if (/404|invalid_link|case_not_found|missing_hash/i.test(message)) return { status: "error", ...INVALID_LINK };
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
  const hash = getIntakeHash();

  useEffect(() => {
    if (!hasTrackedOpen.current) {
      hasTrackedOpen.current = true;
      track("intake_chat_opened");
    }
    if (!hash) {
      setState({ status: "error", ...INVALID_LINK });
      return;
    }
    api
      .invokeFunction<ChatPageData & { error?: string }>("client-intake-chat/chat-get", {
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

  useEffect(() => {
    if (state.status === "ready" && state.data.chat) track("intake_chat_started");
    if (state.status === "ready" && !state.data.chat) track("intake_chat_unavailable");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.status]);

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
            <p>Our assistant guides you through your documents. Drag each PDF into the chat and it is checked right away.</p>
          </div>
          {state.status === "loading" && (
            <div className="app-loader" role="status">
              <div className="app-loader__spinner" />
              <p>Loading your case</p>
            </div>
          )}
          {state.status === "error" && <Notice variant="error" title={state.title} description={state.description} />}
          {state.status === "ready" && (
            <div className="app-layout chat-layout">
              <CaseCard data={state.data} />
              <section className="app-card chat-card" aria-label="Chat with the KB assistant">
                {state.data.chat ? (
                  <ChatPanel config={state.data.chat} hash={hash} />
                ) : (
                  <Notice
                    variant="warning"
                    title="The chat is not available yet"
                    description="Please try again later, or contact your KB advisor."
                  />
                )}
              </section>
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
