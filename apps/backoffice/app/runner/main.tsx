import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@wonderful/ui-base/style.css";
import App from "../src";
import type { WonderfulContext } from "./sdk-shim";

type RunnerBootstrap = {
  context: WonderfulContext;
  proxyPrefix: string;
};

async function loadRunnerConfig(): Promise<RunnerBootstrap> {
  const response = await fetch("/runner-config", {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`failed to load runner config: ${response.status}`);
  }
  return response.json() as Promise<RunnerBootstrap>;
}

function renderApp() {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      {/* The Wonderful host provides the router when embedded; standalone needs its own. */}
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>,
  );
}

void loadRunnerConfig()
  .then((config) => {
    window.__WONDERFUL_RUNNER__ = config;
    renderApp();
  })
  .catch((error: unknown) => {
    const root = document.getElementById("root");
    if (!root) {
      return;
    }
    const message = error instanceof Error ? error.message : String(error);
    root.innerHTML = `<pre style="padding:16px;color:#b91c1c;">${message}</pre>`;
  });
