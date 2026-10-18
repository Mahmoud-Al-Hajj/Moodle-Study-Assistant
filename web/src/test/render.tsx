import type { ReactNode } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { QueryClient } from "@tanstack/react-query";
import { vi } from "vitest";
import { AppProviders } from "../App";

/** JSON reply, or plain text (for file contents) when `text` is set. */
type Reply = { status?: number; body?: unknown; text?: string };
export type Routes = Record<string, Reply | ((init?: RequestInit) => Reply)>;

/** Replaces fetch: keys are "GET /api/session" etc. Returns the mock to inspect calls. */
export function mockApi(routes: Routes) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = decodeURI(String(input).split("?")[0]);
      const key = `${init?.method ?? "GET"} ${url}`;
      const route = routes[key];
      if (!route) throw new Error(`Unmocked request: ${key}`);
      const reply = typeof route === "function" ? route(init) : route;
      if (reply.text !== undefined)
        return new Response(reply.text, {
          status: reply.status ?? 200,
          headers: { "Content-Type": "text/plain; charset=utf-8" },
        });
      return new Response(JSON.stringify(reply.body ?? null), {
        status: reply.status ?? 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function renderWithProviders(ui: ReactNode, route = "/") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <AppProviders client={client}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </AppProviders>,
  );
}
