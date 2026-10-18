import { Box, Stack } from "@mui/material";
import { PageHeader } from "../../components/PageHeader";
import { CourseCard } from "./CourseCard";
import { ScrapeActionCard } from "./ScrapeActionCard";
import { SessionCard } from "./SessionCard";

export function DashboardPage() {
  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Keep your course material up to date."
      />
      <Stack spacing={3}>
        <Box
          sx={{
            display: "grid",
            gap: 3,
            gridTemplateColumns: {
              xs: "1fr",
              md: "minmax(0,2fr) minmax(0,3fr)",
            },
          }}
        >
          <SessionCard />
          <CourseCard />
        </Box>
        <ScrapeActionCard />
      </Stack>
    </>
  );
}
