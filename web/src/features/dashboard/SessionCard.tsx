import { useEffect, useRef } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  LinearProgress,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Typography,
} from "@mui/material";
import LoginRounded from "@mui/icons-material/LoginRounded";
import RefreshRounded from "@mui/icons-material/RefreshRounded";
import { useActiveJob } from "../../api/ActiveJob";
import { useCancelJob, usePressEnter, useSession } from "../../api/queries";
import { ErrorState, LoadingCard } from "../../components/states";
import { StatusChip } from "../../components/StatusChip";
import { JobPanel } from "../../components/JobPanel";
import { fullDate, timeAgo } from "../../components/format";

const NOT_YET = "don't look logged in yet";

export function SessionCard() {
  const session = useSession();
  const { job, start, starting, dismiss } = useActiveJob();
  const cancel = useCancelJob();
  const enter = usePressEnter();
  const autoChecked = useRef(false);
  const busy = starting || job?.state === "running";
  const mine =
    job && (job.action === "login" || job.action === "check_session")
      ? job
      : undefined;

  // First visit: find out whether the saved session still works.
  const status = session.data?.status;
  useEffect(() => {
    if (status === "unknown" && !busy && !autoChecked.current) {
      autoChecked.current = true;
      start.checkSession();
    }
  }, [status, busy, start]);

  if (session.isPending) return <LoadingCard lines={2} />;
  if (session.isError)
    return (
      <ErrorState error={session.error} onRetry={() => session.refetch()} />
    );
  const s = session.data;
  const loggingIn = mine?.action === "login" && mine.state === "running";
  const checking = mine?.action === "check_session" && mine.state === "running";
  const notYet = mine?.lines.some((l) => l.text.includes(NOT_YET)) ?? false;

  return (
    <Card
      component="section"
      aria-labelledby="session-title"
      sx={{ height: "100%" }}
    >
      <CardContent>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
          <Typography
            id="session-title"
            variant="h3"
            component="h2"
            sx={{ flex: 1 }}
          >
            Moodle session
          </Typography>
          <StatusChip status={checking ? "running" : s.status} />
        </Stack>
        <Typography color="text.secondary">
          {checking ? "Checking your saved session…" : s.message}
        </Typography>
        {s.checked_at && !checking && (
          <Typography
            variant="caption"
            color="text.secondary"
            title={fullDate(s.checked_at)}
          >
            Checked {timeAgo(s.checked_at)}
          </Typography>
        )}
        {checking && (
          <LinearProgress sx={{ mt: 2 }} aria-label="Checking session" />
        )}

        {loggingIn ? (
          <Box sx={{ mt: 2 }}>
            <Stepper orientation="vertical" activeStep={1} sx={{ mb: 2 }}>
              <Step>
                <StepLabel>
                  A browser window opened on the Moodle login page
                </StepLabel>
              </Step>
              <Step>
                <StepLabel>Log in there and wait for your dashboard</StepLabel>
              </Step>
              <Step>
                <StepLabel>Come back and press “I'm logged in”</StepLabel>
              </Step>
            </Stepper>
            {notYet && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                You don't look logged in yet. Finish logging in in the browser
                window, then try again.
              </Alert>
            )}
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                onClick={() => enter.mutate(mine.id)}
                disabled={enter.isPending}
              >
                I'm logged in
              </Button>
              <Button
                onClick={() => cancel.mutate(mine.id)}
                disabled={cancel.isPending}
              >
                Cancel
              </Button>
            </Stack>
            <Typography
              variant="caption"
              color="text.secondary"
              component="p"
              sx={{ mt: 1.5 }}
            >
              Your password is typed only into that browser window. This app
              never sees it.
            </Typography>
          </Box>
        ) : (
          <Stack
            direction="row"
            spacing={1}
            sx={{ mt: 2, flexWrap: "wrap", rowGap: 1 }}
          >
            {s.status !== "valid" && (
              <Button
                variant="contained"
                startIcon={<LoginRounded />}
                onClick={start.login}
                disabled={busy}
              >
                Log in to Moodle
              </Button>
            )}
            <Button
              startIcon={<RefreshRounded />}
              onClick={start.checkSession}
              disabled={busy || s.status === "missing"}
            >
              Check now
            </Button>
          </Stack>
        )}

        {mine && mine.state !== "running" && mine.state !== "succeeded" && (
          <Box sx={{ mt: 2 }}>
            <JobPanel
              job={mine}
              onCancel={() => cancel.mutate(mine.id)}
              onDismiss={dismiss}
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
