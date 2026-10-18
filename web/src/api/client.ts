import type { components } from "./schema";

// Types generated from the FastAPI models (npm run gen:api).
export type Session = components["schemas"]["Session"];
export type CourseSummary = components["schemas"]["CourseSummary"];
export type Runs = components["schemas"]["Runs"];
export type RunInfo = components["schemas"]["RunInfo"];
export type Job = components["schemas"]["Job"];
export type JobLine = components["schemas"]["JobLine"];
export type JobState = Job["state"];

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

export const api = {
  session: () => request<Session>("GET", "/api/session"),
  checkSession: () => request<Job>("POST", "/api/session/check"),
  login: () => request<Job>("POST", "/api/session/login"),
  course: () => request<CourseSummary>("GET", "/api/course"),
  runs: () => request<Runs>("GET", "/api/runs"),
  currentJob: () => request<Job | null>("GET", "/api/jobs/current"),
  job: (id: string, after = 0) =>
    request<Job>("GET", `/api/jobs/${id}?after=${after}`),
  startJob: (action: "scrape") => request<Job>("POST", "/api/jobs", { action }),
  cancelJob: (id: string) => request<Job>("POST", `/api/jobs/${id}/cancel`),
  pressEnter: (id: string) => request<Job>("POST", `/api/jobs/${id}/enter`),
};
