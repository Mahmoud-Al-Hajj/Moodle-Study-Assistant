import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  Typography,
} from "@mui/material";
import TravelExploreRounded from "@mui/icons-material/TravelExploreRounded";
import LoginRounded from "@mui/icons-material/LoginRounded";
import { useActiveJob } from "../../api/ActiveJob";
import { useCancelJob, useCourse, useRuns } from "../../api/queries";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { JobPanel } from "../../components/JobPanel";
import { StatusChip } from "../../components/StatusChip";
import { fullDate, timeAgo } from "../../components/format";

export function ScrapeActionCard() {
  const { job, start, starting, dismiss } = useActiveJob();
  const runs = useRuns();
  const course = useCourse();
  const cancel = useCancelJob();
  const [confirm, setConfirm] = useState(false);
  const busy = starting || job?.state === "running";
  const mine = job?.action === "scrape" ? job : undefined;
  const last = runs.data?.scrape;
  const alreadyScraped = course.data?.scraped ?? false;

  return (
    <Card component="section" aria-labelledby="scrape-title">
      <CardContent>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          alignItems={{ sm: "center" }}
        >
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <TravelExploreRounded color="primary" />
              <Typography id="scrape-title" variant="h3" component="h2">
                Scrape course
              </Typography>
            </Stack>
            <Typography color="text.secondary" sx={{ mt: 0.5 }}>
              Reads the course page and updates the list of sections and items.
              Doesn't download files.
            </Typography>
            <Stack
              direction="row"
              spacing={1}
              alignItems="center"
              sx={{ mt: 1 }}
            >
              {last ? (
                <>
                  <StatusChip status={last.state} />
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    title={fullDate(last.finished_at)}
                  >
                    Last run {timeAgo(last.finished_at)}
                    {last.counts.items !== undefined &&
                      ` · ${last.counts.items} items found`}
                  </Typography>
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Not run from this app yet.
                </Typography>
              )}
            </Stack>
          </Box>
          <Button
            variant="contained"
            size="large"
            onClick={() => (alreadyScraped ? setConfirm(true) : start.scrape())}
            disabled={busy}
          >
            {mine?.state === "running" ? "Scraping…" : "Scrape course"}
          </Button>
        </Stack>
        {busy && !mine && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            Another job is running. Only one runs at a time, so Moodle never
            gets parallel requests.
          </Typography>
        )}

        {mine && (
          <Box sx={{ mt: 2 }}>
            <JobPanel
              job={mine}
              onCancel={() => cancel.mutate(mine.id)}
              cancelling={cancel.isPending}
              onDismiss={dismiss}
              resultAction={
                mine.state === "session_expired" && (
                  <Button
                    color="inherit"
                    size="small"
                    startIcon={<LoginRounded />}
                    onClick={start.login}
                  >
                    Log in
                  </Button>
                )
              }
            />
          </Box>
        )}
      </CardContent>
      <ConfirmDialog
        open={confirm}
        title="Scrape the course again?"
        text="This re-reads the course page. Your downloads and their status are kept: new items are added, and items removed from Moodle are dropped from the list."
        confirmLabel="Scrape again"
        onConfirm={start.scrape}
        onClose={() => setConfirm(false)}
      />
    </Card>
  );
}
