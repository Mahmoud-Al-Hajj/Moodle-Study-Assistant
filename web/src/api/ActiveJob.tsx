import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, type Job } from "./client";
import { keys, useCurrentJob, useJob, useJobMutation } from "./queries";
import { useNotify } from "../components/SnackbarProvider";

type ActiveJob = {
  job: Job | undefined;
  start: {
    scrape: () => void;
    download: () => void;
    checkSession: () => void;
    login: () => void;
  };
  starting: boolean;
  dismiss: () => void;
};

const Ctx = createContext<ActiveJob | null>(null);

/** The one job the server can run at a time, shared by every card that can start one. */
export function ActiveJobProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const notify = useNotify();
  const [id, setId] = useState<string | null>(null);
  const current = useCurrentJob();
  const job = useJob(id);
  const lastState = useRef<string | undefined>(undefined);

  // Pick up a job that is already running (page reload, second tab).
  useEffect(() => {
    if (id === null && current.data?.state === "running")
      setId(current.data.id);
  }, [id, current.data]);

  // When the job finishes, refresh what it changed.
  const state = job.data?.state;
  useEffect(() => {
    if (lastState.current === "running" && state && state !== "running") {
      void qc.invalidateQueries({ queryKey: keys.session });
      void qc.invalidateQueries({ queryKey: keys.course });
      void qc.invalidateQueries({ queryKey: keys.runs });
      if (state === "succeeded") notify(`${job.data?.label}: done`, "success");
    }
    lastState.current = state;
  }, [state, qc, notify, job.data?.label]);

  const onStarted = (j: Job) => {
    lastState.current = undefined;
    setId(j.id);
  };
  const onError = (e: Error) => notify(e.message, "error");
  const scrape = useJobMutation(
    () => api.startJob("scrape"),
    onStarted,
    onError,
  );
  const download = useJobMutation(
    () => api.startJob("download"),
    onStarted,
    onError,
  );
  const check = useJobMutation(api.checkSession, onStarted, onError);
  const login = useJobMutation(api.login, onStarted, onError);
  const starting = [scrape, download, check, login].some((m) => m.isPending);

  const value: ActiveJob = {
    job: job.data,
    start: {
      scrape: () => scrape.mutate(undefined),
      download: () => download.mutate(undefined),
      checkSession: () => check.mutate(undefined),
      login: () => login.mutate(undefined),
    },
    starting,
    dismiss: () => setId(null),
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useActiveJob(): ActiveJob {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useActiveJob needs <ActiveJobProvider>");
  return ctx;
}
