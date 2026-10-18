import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { CourseContent, CourseItem } from "../../api/client";
import { mockApi, renderWithProviders, type Routes } from "../../test/render";
import { CoursePage } from "./CoursePage";

const COURSE = "downloads/World Culture";

const item = (over: Partial<CourseItem>): CourseItem => ({
  id: `cm:${over.title}`,
  title: "Untitled",
  type: "resource",
  module: "resource",
  status: "downloaded",
  note: "",
  url: "https://moodle.example/mod/resource/view.php?id=1",
  target_url: "",
  section_name: "Week 1",
  files: [],
  ...over,
});

const file = (path: string, over: object = {}) => ({
  path,
  name: path.split("/").at(-1) as string,
  ext: path.split(".").at(-1) as string,
  size: 2048,
  exists: true,
  text_path: null,
  flags: [],
  openable: true,
  ...over,
});

const content: CourseContent = {
  scraped: true,
  course_id: "959",
  name: "World Culture",
  crawled_at: "2026-10-17T12:00:00+00:00",
  sections: [
    {
      number: 0,
      name: "General",
      items: [
        item({
          title: "Syllabus",
          section_name: "General",
          files: [
            file(`${COURSE}/00-General/Syllabus.docx`, {
              text_path: "data/text/World Culture/00-General/Syllabus.docx.md",
            }),
          ],
        }),
      ],
    },
    {
      number: 1,
      name: "Week 1",
      items: [
        item({
          title: "Lecture slides",
          files: [file(`${COURSE}/01-Week 1/Lecture slides.pdf`)],
        }),
        item({
          title: "Reading list",
          type: "url",
          module: "url",
          target_url: "https://example.org/reading",
        }),
        item({ title: "Schedule", status: "failed", note: "HTTP 404" }),
        item({
          title: "Final exam",
          type: "other",
          module: "quiz",
          status: "unavailable",
          note: "Not available unless: the date is reached",
          url: "",
        }),
      ],
    },
  ],
};

const downloadJob = {
  id: "j2",
  action: "download",
  label: "Download files",
  state: "running",
  started_at: "2026-10-17T12:00:00+00:00",
  finished_at: null,
  exit_code: null,
  message: "",
  progress: { done: 0, total: 1, item: "resource: Schedule" },
  waiting_for_input: false,
  lines: [],
  next: 0,
};

function routes(overrides: Routes = {}): Routes {
  return {
    "GET /api/course/items": { body: content },
    "GET /api/jobs/current": { body: null },
    ...overrides,
  };
}

afterEach(() => vi.unstubAllGlobals());

const row = (title: string) =>
  screen.getByText(title).closest("tr") as HTMLElement;

describe("CoursePage", () => {
  it("lists sections with icons, statuses, notes and links", async () => {
    mockApi(routes());
    renderWithProviders(<CoursePage />);
    expect(
      await screen.findByRole("heading", { name: "World Culture" }),
    ).toBeInTheDocument();
    expect(screen.getByText("00 · General")).toBeInTheDocument();
    expect(screen.getByText("01 · Week 1")).toBeInTheDocument();
    expect(within(row("Schedule")).getByText("HTTP 404")).toBeInTheDocument();
    expect(
      within(row("Final exam")).getAllByText("Unavailable")[0],
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reading list" })).toHaveAttribute(
      "href",
      "https://example.org/reading",
    );
    expect(
      screen.getByRole("link", { name: "Open Lecture slides in Moodle" }),
    ).toHaveAttribute("target", "_blank");
    expect(screen.getByTitle("File (pdf)")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /retry 1 failed/i }),
    ).toBeEnabled();
  });

  it("points to the dashboard when the course isn't scraped", async () => {
    mockApi(
      routes({
        "GET /api/course/items": {
          body: { ...content, scraped: false, name: null, sections: [] },
        },
      }),
    );
    renderWithProviders(<CoursePage />);
    expect(
      await screen.findByText("This course hasn't been scraped yet"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Go to the dashboard" }),
    ).toHaveAttribute("href", "/");
  });

  it("shows a friendly error with Retry", async () => {
    let calls = 0;
    mockApi(
      routes({
        "GET /api/course/items": () =>
          ++calls === 1
            ? { status: 500, body: { error: "Something went wrong." } }
            : { body: content },
      }),
    );
    renderWithProviders(<CoursePage />);
    expect(await screen.findByText("Something went wrong.")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "World Culture" }),
    ).toBeInTheDocument();
  });

  it("filters by type and search, and clears the filters", async () => {
    mockApi(routes());
    renderWithProviders(<CoursePage />);
    await screen.findByText("Syllabus");

    const link = screen.getByRole("button", { name: "Link 1" });
    await userEvent.click(link);
    expect(link).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Showing 1 of 5 items")).toBeInTheDocument();
    expect(screen.queryByText("Syllabus")).not.toBeInTheDocument();
    expect(screen.queryByText("00 · General")).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Search titles"), "zzz");
    expect(screen.getByText("No items match")).toBeInTheDocument();
    await userEvent.click(
      screen.getAllByRole("button", { name: "Clear filters" })[0],
    );
    expect(screen.getByText("Syllabus")).toBeInTheDocument();
    expect(screen.getByText("5 items")).toBeInTheDocument();
  });

  it("reads the filters from the URL", async () => {
    mockApi(routes());
    renderWithProviders(<CoursePage />, "/course?status=failed");
    expect(await screen.findByText("Schedule")).toBeInTheDocument();
    expect(screen.queryByText("Lecture slides")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Failed 1" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("previews a Word file's extracted text and opens it in its app", async () => {
    const fetchMock = mockApi(
      routes({
        "GET /api/files/data/text/World Culture/00-General/Syllabus.docx.md": {
          text: "# Syllabus\nWeek 1: Adam Smith",
        },
        "POST /api/files/open": { body: { ok: true } },
      }),
    );
    renderWithProviders(<CoursePage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Syllabus" }),
    );
    const panel = await screen.findByRole("dialog", { name: "Syllabus" });
    expect(
      await within(panel).findByText(/Week 1: Adam Smith/),
    ).toBeInTheDocument();
    expect(within(panel).getByText(/Extracted text/)).toBeInTheDocument();

    await userEvent.click(
      within(panel).getByRole("button", { name: "Open in app" }),
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/files/open",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ path: `${COURSE}/00-General/Syllabus.docx` }),
        }),
      ),
    );
    expect(await screen.findByText("Opening Syllabus.docx…")).toBeVisible();

    await userEvent.click(
      within(panel).getByRole("button", { name: "Close preview" }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });

  it("shows a PDF in the browser's viewer", async () => {
    mockApi(routes());
    renderWithProviders(<CoursePage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Preview Lecture slides" }),
    );
    const frame = await screen.findByTitle("Lecture slides.pdf");
    expect(frame).toHaveAttribute(
      "src",
      "/api/files/downloads/World%20Culture/01-Week%201/Lecture%20slides.pdf",
    );
  });

  it("retries failed items with the download job", async () => {
    const fetchMock = mockApi(
      routes({
        "POST /api/jobs": { status: 202, body: downloadJob },
        "GET /api/jobs/j2": { body: downloadJob },
      }),
    );
    renderWithProviders(<CoursePage />);
    await userEvent.click(
      await screen.findByRole("button", { name: /retry 1 failed/i }),
    );
    expect(await screen.findByText("Download files")).toBeInTheDocument();
    expect(screen.getByText("0 of 1: resource: Schedule")).toBeInTheDocument();
    const [, init] = fetchMock.mock.calls.find(
      ([url, i]) => url === "/api/jobs" && i?.method === "POST",
    ) as [string, RequestInit];
    expect(init.body).toBe(JSON.stringify({ action: "download" }));
    expect(init.headers).toMatchObject({ "X-Moodle-Study": "1" });
    expect(
      screen.getByRole("button", { name: /retry 1 failed/i }),
    ).toBeDisabled();
  });
});
