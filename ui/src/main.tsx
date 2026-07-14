import React from "react";
import ReactDOM from "react-dom/client";
import "@patternfly/react-core/dist/styles/base.css";
import App from "./App";
import "./theme.css";

// biome-ignore lint/style/noNonNullAssertion: root element is always present in index.html
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
