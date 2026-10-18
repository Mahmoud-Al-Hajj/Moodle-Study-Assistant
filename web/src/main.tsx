import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { AppProviders, AppRoutes, newQueryClient } from "./App";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <AppProviders client={newQueryClient()}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AppProviders>
  </StrictMode>,
);
