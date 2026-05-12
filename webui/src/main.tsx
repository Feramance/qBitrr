import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import App from "./App";

const rootElement = document.getElementById("root");
// #region agent log
fetch("http://localhost:7570/ingest/7948a40e-b2fc-4344-8340-1c34d1fbd429", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "509483" },
  body: JSON.stringify({
    sessionId: "509483",
    runId: "initial",
    hypothesisId: "H1",
    location: "webui/src/main.tsx:7",
    message: "webui bootstrap reached",
    data: { hasRootElement: Boolean(rootElement), path: window.location.pathname },
    timestamp: Date.now(),
  }),
}).catch(() => {});
// #endregion

window.addEventListener("error", event => {
  // #region agent log
  fetch("http://localhost:7570/ingest/7948a40e-b2fc-4344-8340-1c34d1fbd429", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "509483" },
    body: JSON.stringify({
      sessionId: "509483",
      runId: "initial",
      hypothesisId: "H2",
      location: "webui/src/main.tsx:22",
      message: "window error event",
      data: { message: event.message, filename: event.filename, lineno: event.lineno, colno: event.colno },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion
});

window.addEventListener("unhandledrejection", event => {
  // #region agent log
  fetch("http://localhost:7570/ingest/7948a40e-b2fc-4344-8340-1c34d1fbd429", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "509483" },
    body: JSON.stringify({
      sessionId: "509483",
      runId: "initial",
      hypothesisId: "H2",
      location: "webui/src/main.tsx:38",
      message: "unhandled promise rejection",
      data: { reason: String(event.reason) },
      timestamp: Date.now(),
    }),
  }).catch(() => {});
  // #endregion
});

if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
}
