import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockApi, renderWithProviders, type Routes } from "../../test/render";
import { DashboardPage } from "./DashboardPage";

const scrapedCourse = {
  configured: true,
  course_id: "959",
  course_url: "https://moodle.example/moodle/course/view.php?id=959",
  scraped: true,
  name: "World Culture",
  crawled_at: "2026-10-17T12:00:00+00:00",
  sections: 8,
  items: 64,
  by_status: { downloaded: 62, failed: 1, skipped: 1 },
  by_type: { resource: 40 },
};

const job = {
  id: "j1",
  action: "scrape",
  label: "Scrape course",
  state: "running",
  started_at: "2026-10-17T12:00:00+00:00",
  finished_at: null,
  exit_code: null,
  message: "",
  progress: null,
  waiting_for_input: false,
  lines: [{ seq: 1, level: "info", text: "Opening the course page" }],
  next: 1,
};

function routes(overrides: Routes = {}): Routes {
  return {
    "GET /api/session": {
      body: {
        status: "valid",
        checked_at: null,
        message: "You are logged in.",
      },
    },
    "GET /api/course": { body: scrapedCourse },
    "GET /api/runs": { body: {} },
    "GET /api/jobs/current": { body: null },
    "GET /api/jobs/j1": { body: job },
    ...overrides,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("DashboardPage", () => {
  it("shows a valid session and the scraped course with its counts", async () => {
    mockApi(routes());
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText("World Culture")).toBeInTheDocument();
    expect(screen.getByText("Logged in")).toBeInTheDocument();
    expect(screen.getByText("62")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /open the course in moodle/i }),
    ).toHaveAttribute("href", scrapedCourse.course_url);
    expect(
      screen.queryByRole("button", { name: /log in to moodle/i }),
    ).not.toBeInTheDocument();
  });

  it("asks before scraping again, then starts the job with the API header", async () => {
    const fetchMock = mockApi(
      routes({ "POST /api/jobs": { status: 202, body: job } }),
    );
    renderWithProviders(<DashboardPage />);
    await screen.findByText("World Culture");
    const scrapeCard = screen
      .getByRole("heading", { name: "Scrape course" })
      .closest("section") as HTMLElement;
    await userEvent.click(
      within(scrapeCard).getByRole("button", { name: "Scrape course" }),
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Scrape again" }),
    );
    // The running job's panel appears in the card, with progress and Cancel.
    expect(
      await within(scrapeCard).findByRole("button", { name: "Cancel" }),
    ).toBeInTheDocument();
    expect(
      within(scrapeCard).getByRole("progressbar", {
        name: "Scrape course progress",
      }),
    ).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(post?.[0]).toBe("/api/jobs");
    expect(new Headers(post?.[1]?.headers).get("X-Moodle-Study")).toBe("1");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ action: "scrape" });
  });

  it("offers to log in when the session expired", async () => {
    mockApi(
      routes({
        "GET /api/session": {
          body: {
            status: "expired",
            checked_at: "2026-10-17T12:00:00+00:00",
            message: "Your session has expired. Log in again.",
          },
        },
      }),
    );
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText("Session expired")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /log in to moodle/i }),
    ).toBeEnabled();
  });

  it("guides a first run: not logged in, course not scraped yet", async () => {
    mockApi(
      routes({
        "GET /api/session": {
          body: {
            status: "missing",
            checked_at: null,
            message: "You haven't logged in yet.",
          },
        },
        "GET /api/course": {
          body: {
            ...scrapedCourse,
            scraped: false,
            name: null,
            items: 0,
            by_status: {},
          },
        },
      }),
    );
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText("Not logged in")).toBeInTheDocument();
    expect(
      await screen.findByText("Course 959 isn't scraped yet"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check now" })).toBeDisabled();
  });

  it("shows a friendly error with Retry when the server can't answer", async () => {
    let calls = 0;
    mockApi(
      routes({
        "GET /api/course": () =>
          ++calls === 1
            ? {
                status: 500,
                body: {
                  error: "Something went wrong in the local server. Try again.",
                },
              }
            : { body: scrapedCourse },
      }),
    );
    renderWithProviders(<DashboardPage />);
    expect(
      await screen.findByText(
        "Something went wrong in the local server. Try again.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("World Culture")).toBeInTheDocument();
  });
});
