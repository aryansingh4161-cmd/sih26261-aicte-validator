import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource/montserrat/600.css";
import "@fontsource/montserrat/700.css";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto-mono/400.css";
import "@fontsource/roboto-mono/500.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";
import { detectMode } from "./data/client";
import { SettingsProvider } from "./app/settings";
import { App } from "./App";

const qc = new QueryClient();
detectMode().then(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={qc}>
        <SettingsProvider><App /></SettingsProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
});
