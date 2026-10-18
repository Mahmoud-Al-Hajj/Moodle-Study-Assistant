import type { components } from "./schema";

// Types generated from the FastAPI models (npm run gen:api).
export type Session = components["schemas"]["Session"];
export type CourseSummary = components["schemas"]["CourseSummary"];
export type Runs = components["schemas"]["Runs"];
export type RunInfo = components["schemas"]["RunInfo"];
export type Job = components["schemas"]["Job"];
export type JobLine = components["schemas"]["JobLine"];
export type JobState = Job["state"];
export type JobAction = components["schemas"]["StartJob"]["action"];
export type CourseContent = components["schemas"]["CourseContent"];
export type CourseSection = components["schemas"]["CourseSection"];
export type CourseItem = components["schemas"]["CourseItem"];
export type ItemFile = components["schemas"]["ItemFile"];

/** A failure with a message that is safe and friendly to show as-is. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(
  method: "GET" | "POST",
  path: string,
  body?: unknown,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers: {
        Accept: "application/json",
        // Required by the API for every change: other websites can't send it.
        ...(method === "POST" ? { "X-Moodle-Study": "1" } : {}),
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(
      "Can't reach the local server. Is it still running? Start it with .\\dev",
      0,
    );
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const message =
      data && typeof data.error === "string"
        ? data.error
        : `The local server answered ${res.status}.`;
    throw new ApiError(message, res.status);
  }
  return data as T;
}

/** URL of a file under downloads/ or data/text/ (paths come from the API, relative to the project). */
export const fileUrl = (path: string) =>
  "/api/files/" + path.split("/").map(encodeURIComponent).join("/");

async function fetchText(path: string): Promise<string> {
  let res: Response;
  try {
    res = await fetch(fileUrl(path));
  } catch {
    throw new ApiError("Can't reach the local server. Is it still running?", 0);
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(
      data?.error ?? `The local server answered ${res.status}.`,
      res.status,
    );
  }
  return res.text();
}

export const api = {
  session: () => request<Session>("GET", "/api/session"),
  checkSession: () => request<Job>("POST", "/api/session/check"),
  login: () => request<Job>("POST", "/api/session/login"),
  course: () => request<CourseSummary>("GET", "/api/course"),
  courseItems: () => request<CourseContent>("GET", "/api/course/items"),
  fileText: fetchText,
  openFile: (path: string) =>
    request<{ ok: boolean }>("POST", "/api/files/open", { path }),
  revealFile: (path: string) =>
    request<{ ok: boolean }>("POST", "/api/files/reveal", { path }),
  runs: () => request<Runs>("GET", "/api/runs"),
  currentJob: () => request<Job | null>("GET", "/api/jobs/current"),
  job: (id: string, after = 0) =>
    request<Job>("GET", `/api/jobs/${id}?after=${after}`),
  startJob: (action: JobAction) =>
    request<Job>("POST", "/api/jobs", { action }),
  cancelJob: (id: string) => request<Job>("POST", `/api/jobs/${id}/cancel`),
  pressEnter: (id: string) => request<Job>("POST", `/api/jobs/${id}/enter`),
};
