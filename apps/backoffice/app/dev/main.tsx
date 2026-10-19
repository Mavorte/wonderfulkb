import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@wonderful/ui-base/style.css";
import App from "../src";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {/* The Wonderful host provides the router when embedded; standalone needs its own. */}
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
