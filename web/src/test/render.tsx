import type { ReactNode } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { QueryClient } from "@tanstack/react-query";
import { vi } from "vitest";
import { AppProviders } from "../App";

type Reply = { status?: number; body: unknown };
export type Routes = Record<string, Reply | ((init?: RequestInit) => Reply)>;

/** Replaces fetch: keys are "GET /api/session" etc. Returns the mock to inspect calls. */
export function mockApi(routes: Routes) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input).split("?")[0];
      const key = `${init?.method ?? "GET"} ${url}`;
      const route = routes[key];
      if (!route) throw new Error(`Unmocked request: ${key}`);
      const reply = typeof route === "function" ? route(init) : route;
      return new Response(JSON.stringify(reply.body), {
        status: reply.status ?? 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function renderWithProviders(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <AppProviders client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </AppProviders>,
  );
}
