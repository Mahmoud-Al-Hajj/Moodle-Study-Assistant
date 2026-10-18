import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "@mui/material";
import { theme } from "../theme/theme";
import type { Job } from "../api/client";
import { JobPanel } from "./JobPanel";

const base: Job = {
  id: "j1",
  action: "scrape",
  label: "Scrape course",
  state: "running",
  started_at: "2026-10-17T12:00:00+00:00",
  finished_at: null,
  exit_code: null,
  message: "",
  progress: { done: 3, total: 12, item: "resource: Lecture 1 slides" },
  waiting_for_input: false,
  lines: [
    { seq: 1, level: "info", text: "Downloading 12 item(s)" },
    { seq: 2, level: "warning", text: "Something odd" },
  ],
  next: 2,
};

const renderPanel = (job: Job, props = {}) =>
  render(
    <ThemeProvider theme={theme}>
      <JobPanel job={job} onCancel={() => {}} {...props} />
    </ThemeProvider>,
  );

describe("JobPanel", () => {
  it("shows determinate progress and the current item", () => {
    renderPanel(base);
    expect(
      screen.getByRole("progressbar", { name: "Scrape course progress" }),
    ).toHaveAttribute("aria-valuenow", "25");
    expect(
      screen.getByText("3 of 12: resource: Lecture 1 slides"),
    ).toBeInTheDocument();
  });

  it("toggles the live log", async () => {
    renderPanel(base);
    const toggle = screen.getByRole("button", { name: "Show log (2 lines)" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(toggle);
    expect(screen.getByRole("button", { name: "Hide log" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(
      screen.getByRole("log", { name: "Scrape course log" }),
    ).toHaveTextContent("Something odd");
  });

  it("cancels a running job", async () => {
    const onCancel = vi.fn();
    renderPanel(base, { onCancel });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("points to the log when a successful job left warnings", () => {
    renderPanel({
      ...base,
      state: "succeeded",
      progress: null,
      message: "Done.",
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Done, with 1 warning. Open the log to read it.",
    );
  });

  it("shows the result of a finished job and can be closed", async () => {
    const onDismiss = vi.fn();
    renderPanel(
      {
        ...base,
        state: "failed",
        progress: null,
        message: "Moodle says: course not found",
      },
      { onDismiss },
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Moodle says: course not found",
    );
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
