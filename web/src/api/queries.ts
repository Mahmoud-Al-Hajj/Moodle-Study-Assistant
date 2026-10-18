import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Job } from "./client";

export const keys = {
  session: ["session"] as const,
  course: ["course"] as const,
  runs: ["runs"] as const,
  currentJob: ["job", "current"] as const,
  job: (id: string | null) => ["job", id] as const,
};

const MAX_LINES = 2000;

export const useSession = () =>
  useQuery({ queryKey: keys.session, queryFn: api.session });
export const useCourse = () =>
  useQuery({ queryKey: keys.course, queryFn: api.course });
export const useRuns = () =>
  useQuery({ queryKey: keys.runs, queryFn: api.runs });
export const useCurrentJob = () =>
  useQuery({ queryKey: keys.currentJob, queryFn: api.currentJob });

/** Follows one job: polls each second while it runs, fetching only new log lines. */
export function useJob(id: string | null) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: keys.job(id),
    enabled: id !== null,
    queryFn: async () => {
      const prev = qc.getQueryData<Job>(keys.job(id));
      const next = await api.job(id as string, prev?.next ?? 0);
      if (!prev) return next;
      // Keep only lines we haven't seen: overlapping polls must never duplicate the log.
      const lastSeq = prev.lines.at(-1)?.seq ?? 0;
      const fresh = next.lines.filter((l) => l.seq > lastSeq);
      return { ...next, lines: [...prev.lines, ...fresh].slice(-MAX_LINES) };
    },
    refetchInterval: (q) => (q.state.data?.state === "running" ? 1000 : false),
  });
}

/** Starting any job: the result seeds the job's cache so polling continues from it. */
export function useJobMutation<A>(
  fn: (arg: A) => Promise<Job>,
  onStarted: (job: Job) => void,
  onError: (error: Error) => void,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (job) => {
      qc.setQueryData(keys.job(job.id), job);
      onStarted(job);
    },
    onError,
  });
}

export function useCancelJob() {
  return useMutation({ mutationFn: (id: string) => api.cancelJob(id) });
}

export function usePressEnter() {
  return useMutation({ mutationFn: (id: string) => api.pressEnter(id) });
}
