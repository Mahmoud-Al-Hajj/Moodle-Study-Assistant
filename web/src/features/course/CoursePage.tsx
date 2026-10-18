import { useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router";
import { Box, Button, Stack, Tooltip, Typography } from "@mui/material";
import TravelExploreRounded from "@mui/icons-material/TravelExploreRounded";
import SearchOffRounded from "@mui/icons-material/SearchOffRounded";
import ReplayRounded from "@mui/icons-material/ReplayRounded";
import LoginRounded from "@mui/icons-material/LoginRounded";
import { useActiveJob } from "../../api/ActiveJob";
import { useCancelJob, useCourseItems } from "../../api/queries";
import { JobPanel } from "../../components/JobPanel";
import { PageHeader } from "../../components/PageHeader";
import { EmptyState, ErrorState, LoadingCard } from "../../components/states";
import { timeAgo } from "../../components/format";
import { FilePreview } from "./FilePreview";
import { FilterBar } from "./FilterBar";
import { SectionList } from "./SectionList";
import {
  filterSections,
  isFiltering,
  parseFilters,
  toParams,
  type Filters,
} from "./filters";

const TITLE = "Course content";

function RetryFailed({ failed }: { failed: number }) {
  const { job, start, starting } = useActiveJob();
  const busy = starting || job?.state === "running";
  if (failed === 0) return null;
  return (
    <Tooltip
      title={
        busy
          ? "Another job is running. Only one runs at a time."
          : "Downloads the failed items again, plus anything new in the list. Doesn't re-read the course page."
      }
    >
      {/* span: a disabled button still shows its tooltip */}
      <span>
        <Button
          variant="contained"
          startIcon={<ReplayRounded />}
          onClick={start.download}
          disabled={busy}
        >
          Retry {failed} failed
        </Button>
      </span>
    </Tooltip>
  );
}

function DownloadJob() {
  const { job, start, dismiss } = useActiveJob();
  const cancel = useCancelJob();
  if (job?.action !== "download") return null;
  return (
    <Box sx={{ mb: 3 }}>
      <JobPanel
        job={job}
        onCancel={() => cancel.mutate(job.id)}
        cancelling={cancel.isPending}
        onDismiss={dismiss}
        resultAction={
          job.state === "session_expired" && (
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
  );
}

export function CoursePage() {
  const content = useCourseItems();
  const [params, setParams] = useSearchParams();
  // State is the source of truth; the URL only mirrors it (React Router updates the URL in a
  // transition, so reading filters back from it would lose fast keystrokes).
  const [filters, setFilterState] = useState(() => parseFilters(params));
  const setFilters = (f: Filters) => {
    setFilterState(f);
    setParams(toParams(f), { replace: true });
  };
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [previewId, setPreviewId] = useState<string | null>(null);

  if (content.isPending)
    return (
      <>
        <PageHeader title={TITLE} />
        <Stack spacing={2}>
          <LoadingCard />
          <LoadingCard />
        </Stack>
      </>
    );
  if (content.isError)
    return (
      <>
        <PageHeader title={TITLE} />
        <ErrorState error={content.error} onRetry={() => content.refetch()} />
      </>
    );

  const data = content.data;
  if (!data.scraped)
    return (
      <>
        <PageHeader title={TITLE} />
        <EmptyState
          icon={<TravelExploreRounded />}
          title="This course hasn't been scraped yet"
          text="Scrape it on the Dashboard to list its sections and items here."
          action={
            <Button component={RouterLink} to="/" variant="contained">
              Go to the dashboard
            </Button>
          }
        />
      </>
    );

  const items = data.sections.flatMap((s) => s.items);
  const failed = items.filter((it) => it.status === "failed").length;
  const visible = filterSections(data.sections, filters);
  const shown = visible.reduce((n, s) => n + s.items.length, 0);
  const filtering = isFiltering(filters);
  const preview = items.find((it) => it.id === previewId) ?? null;
  const toggle = (n: number) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (!next.delete(n)) next.add(n);
      return next;
    });

  return (
    <>
      <PageHeader
        title={data.name ?? TITLE}
        subtitle={`${data.sections.length} sections · ${items.length} items · scraped ${timeAgo(data.crawled_at)}`}
        actions={<RetryFailed failed={failed} />}
      />
      <DownloadJob />
      <FilterBar items={items} filters={filters} onChange={setFilters} />

      <Stack
        direction="row"
        spacing={1}
        sx={{ mb: 1.5, alignItems: "center", flexWrap: "wrap" }}
      >
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ flex: 1 }}
          aria-live="polite"
        >
          {filtering
            ? `Showing ${shown} of ${items.length} items`
            : `${items.length} items`}
        </Typography>
        <Button size="small" onClick={() => setCollapsed(new Set())}>
          Expand all
        </Button>
        <Button
          size="small"
          onClick={() =>
            setCollapsed(new Set(data.sections.map((s) => s.number)))
          }
        >
          Collapse all
        </Button>
      </Stack>

      {visible.length === 0 ? (
        <EmptyState
          icon={<SearchOffRounded />}
          title="No items match"
          text="Try another word, or turn off some of the type and status filters."
          action={
            <Button
              variant="outlined"
              onClick={() => setFilters({ q: "", types: [], statuses: [] })}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <SectionList
          sections={visible}
          filtering={filtering}
          collapsed={collapsed}
          onToggle={toggle}
          onPreview={(it) => setPreviewId(it.id)}
        />
      )}
      <FilePreview item={preview} onClose={() => setPreviewId(null)} />
    </>
  );
}
