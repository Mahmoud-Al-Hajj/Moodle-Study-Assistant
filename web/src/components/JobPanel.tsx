import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import {
  Alert,
  Box,
  Button,
  Collapse,
  LinearProgress,
  Stack,
  Typography,
  type AlertColor,
} from "@mui/material";
import ExpandMoreRounded from "@mui/icons-material/ExpandMoreRounded";
import ExpandLessRounded from "@mui/icons-material/ExpandLessRounded";
import type { Job, JobState } from "../api/client";
import { monoFamily } from "../theme/theme";
import { StatusChip } from "./StatusChip";

const RESULT: Record<JobState, AlertColor> = {
  running: "info",
  succeeded: "success",
  failed: "error",
  session_expired: "warning",
  cancelled: "info",
};

/** Live view of a running or finished job: progress, current step, collapsible log, cancel. */
export function JobPanel({
  job,
  onCancel,
  cancelling = false,
  onDismiss,
  resultAction,
}: {
  job: Job;
  onCancel: () => void;
  cancelling?: boolean;
  onDismiss?: () => void;
  resultAction?: ReactNode;
}) {
  const running = job.state === "running";
  const [showLog, setShowLog] = useState(false);
  const logId = useId();
  const logRef = useRef<HTMLDivElement>(null);
  const lastInfo =
    [...job.lines].reverse().find((l) => l.level !== "output")?.text ??
    "Starting…";
  const warnings = job.lines.filter((l) => l.level === "warning").length;
  const pct =
    job.progress && job.progress.total > 0
      ? (100 * job.progress.done) / job.progress.total
      : null;

  useEffect(() => {
    const el = logRef.current;
    if (el && showLog) el.scrollTop = el.scrollHeight;
  }, [job.lines.length, showLog]);

  return (
    <Box sx={{ borderTop: 1, borderColor: "divider", pt: 2 }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="subtitle1" component="h4" sx={{ flex: 1 }}>
          {job.label}
        </Typography>
        <StatusChip status={job.state} />
      </Stack>

      {running && (
        <Box sx={{ mb: 1.5 }}>
          <LinearProgress
            variant={pct === null ? "indeterminate" : "determinate"}
            value={pct ?? undefined}
            aria-label={`${job.label} progress`}
          />
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mt: 1 }}
            noWrap
          >
            {job.progress
              ? `${job.progress.done} of ${job.progress.total}: ${job.progress.item}`
              : lastInfo}
          </Typography>
        </Box>
      )}

      {!running && (
        <Alert
          severity={
            job.state === "succeeded" && warnings > 0
              ? "warning"
              : RESULT[job.state]
          }
          sx={{ mb: 1.5 }}
          action={resultAction}
        >
          {job.state === "succeeded" && warnings > 0
            ? `Done, with ${warnings} warning${warnings > 1 ? "s" : ""}. Open the log to read ${warnings > 1 ? "them" : "it"}.`
            : job.message}
        </Alert>
      )}

      <Stack direction="row" spacing={1} alignItems="center">
        <Button
          size="small"
          onClick={() => setShowLog((v) => !v)}
          aria-expanded={showLog}
          aria-controls={logId}
          endIcon={showLog ? <ExpandLessRounded /> : <ExpandMoreRounded />}
        >
          {showLog ? "Hide log" : `Show log (${job.lines.length} lines)`}
        </Button>
        <Box sx={{ flex: 1 }} />
        {running ? (
          <Button
            size="small"
            color="error"
            variant="outlined"
            onClick={onCancel}
            disabled={cancelling}
          >
            {cancelling ? "Cancelling…" : "Cancel"}
          </Button>
        ) : (
          onDismiss && (
            <Button size="small" onClick={onDismiss}>
              Close
            </Button>
          )
        )}
      </Stack>

      <Collapse in={showLog}>
        <Box
          id={logId}
          ref={logRef}
          role="log"
          aria-live="polite"
          aria-label={`${job.label} log`}
          tabIndex={0}
          sx={{
            mt: 1,
            p: 1.5,
            maxHeight: (t) => t.layout.logMaxHeight,
            overflowY: "auto",
            bgcolor: "action.hover",
            borderRadius: 1,
            fontFamily: monoFamily,
            typography: "caption",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {job.lines.map((l) => (
            <Box
              key={l.seq}
              sx={{
                color:
                  l.level === "error"
                    ? "error.main"
                    : l.level === "warning"
                      ? "warning.main"
                      : "text.primary",
              }}
            >
              {l.text}
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}
