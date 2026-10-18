import {
  Box,
  Button,
  Card,
  CardContent,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import OpenInNewRounded from "@mui/icons-material/OpenInNewRounded";
import TravelExploreRounded from "@mui/icons-material/TravelExploreRounded";
import SettingsSuggestOutlined from "@mui/icons-material/SettingsSuggestOutlined";
import { useActiveJob } from "../../api/ActiveJob";
import { useCourse } from "../../api/queries";
import { EmptyState, ErrorState, LoadingCard } from "../../components/states";
import { Stat } from "../../components/Stat";
import { fullDate, timeAgo } from "../../components/format";

export function CourseCard() {
  const course = useCourse();
  const { job, start, starting } = useActiveJob();
  const busy = starting || job?.state === "running";

  if (course.isPending) return <LoadingCard lines={3} />;
  if (course.isError)
    return <ErrorState error={course.error} onRetry={() => course.refetch()} />;
  const c = course.data;

  return (
    <Card
      component="section"
      aria-labelledby="course-title"
      sx={{ height: "100%" }}
    >
      <CardContent>
        <Typography variant="overline" color="text.secondary" component="p">
          Current course
        </Typography>
        {!c.configured ? (
          <EmptyState
            icon={<SettingsSuggestOutlined />}
            title="No course configured"
            text="Set MOODLE_URL and COURSE_ID in the .env file, then reload this page. (Editing them here comes with the Settings screen.)"
          />
        ) : !c.scraped ? (
          <EmptyState
            icon={<TravelExploreRounded />}
            title={`Course ${c.course_id} isn't scraped yet`}
            text="Scraping reads the course page and lists every section and item. Nothing is downloaded yet."
            action={
              <Button
                variant="contained"
                onClick={start.scrape}
                disabled={busy}
              >
                Scrape course
              </Button>
            }
          />
        ) : (
          <>
            <Stack direction="row" spacing={1} alignItems="flex-start">
              <Typography
                id="course-title"
                variant="h2"
                sx={{ flex: 1, minWidth: 0 }}
              >
                {c.name}
              </Typography>
              {c.course_url && (
                <Tooltip title="Open the course in Moodle">
                  <IconButton
                    component="a"
                    href={c.course_url}
                    target="_blank"
                    rel="noreferrer"
                    aria-label="Open the course in Moodle (new tab)"
                  >
                    <OpenInNewRounded />
                  </IconButton>
                </Tooltip>
              )}
            </Stack>
            <Typography variant="body2" color="text.secondary">
              Course {c.course_id} · {c.sections} sections
              {c.crawled_at && (
                <span title={fullDate(c.crawled_at)}>
                  {" "}
                  · scraped {timeAgo(c.crawled_at)}
                </span>
              )}
            </Typography>
            <Box
              sx={{
                mt: 3,
                display: "grid",
                gap: 2,
                gridTemplateColumns: {
                  xs: "repeat(2, 1fr)",
                  sm: "repeat(5, 1fr)",
                },
              }}
            >
              <Stat label="Found" value={c.items} />
              <Stat
                label="Downloaded"
                value={c.by_status.downloaded ?? 0}
                tone="success"
              />
              <Stat label="Pending" value={c.by_status.pending ?? 0} />
              <Stat
                label="Failed"
                value={c.by_status.failed ?? 0}
                tone="error"
              />
              <Stat
                label="Unavailable"
                value={c.by_status.unavailable ?? 0}
                tone="warning"
              />
            </Box>
          </>
        )}
      </CardContent>
    </Card>
  );
}
