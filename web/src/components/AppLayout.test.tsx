import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockApi, renderWithProviders } from "../test/render";
import { AppLayout } from "./AppLayout";

afterEach(() => vi.unstubAllGlobals());

describe("AppLayout", () => {
  it("has a skip link, labelled icon buttons and a main navigation", async () => {
    mockApi({ "GET /api/jobs/current": { body: null } });
    // jsdom has no wide screen, so this renders the small-screen layout (drawer).
    renderWithProviders(<AppLayout>content</AppLayout>);
    expect(
      screen.getByRole("link", { name: "Skip to content" }),
    ).toHaveAttribute("href", "#main");
    expect(
      screen.getByRole("button", { name: /switch to (dark|light) mode/i }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Open navigation" }),
    );

    const nav = await screen.findByRole("navigation", { name: "Main" });
    expect(
      within(nav).getByRole("link", { name: "Dashboard" }),
    ).toHaveAttribute("aria-current", "page");
    // Screens from later stages are listed but can't be opened yet.
    const later = within(nav).getByRole("link", { name: /Course content/ });
    expect(later).toHaveAttribute("aria-disabled", "true");
    expect(later).toHaveTextContent("Coming in stage B");
  });
});
