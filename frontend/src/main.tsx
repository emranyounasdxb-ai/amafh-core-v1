import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { capturePasswordLink } from "./app/session/passwordLink";

// Strip the secret before rendering or session-provider API requests.
capturePasswordLink();
window.addEventListener("popstate", capturePasswordLink);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
