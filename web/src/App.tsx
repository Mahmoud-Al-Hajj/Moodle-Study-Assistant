import type { ReactNode } from "react";
import { Route, Routes, Link as RouterLink } from "react-router";
import { Button, CssBaseline, ThemeProvider } from "@mui/material";
import ExploreOffOutlined from "@mui/icons-material/ExploreOffOutlined";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { theme } from "./theme/theme";
import { SnackbarProvider } from "./components/SnackbarProvider";
import { ActiveJobProvider } from "./api/ActiveJob";
import { AppLayout } from "./components/AppLayout";
import { EmptyState } from "./components/states";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { CoursePage } from "./features/course/CoursePage";

export const newQueryClient = () =>
  new QueryClient({
    defaultOptions: { queries: { retry: 1, staleTime: 5_000 } },
  });

/** Everything the screens need around them; tests wrap screens in this too. */
export function AppProviders({
  client,
  children,
}: {
  client: QueryClient;
  children: ReactNode;
}) {
  return (
    <ThemeProvider theme={theme} defaultMode="system">
      <CssBaseline enableColorScheme />
      <QueryClientProvider client={client}>
        <SnackbarProvider>
          <ActiveJobProvider>{children}</ActiveJobProvider>
        </SnackbarProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

function NotFound() {
  return (
    <EmptyState
      icon={<ExploreOffOutlined />}
      title="This page doesn't exist yet"
      text="It may come in a later stage. The dashboard has everything that works today."
      action={
        <Button component={RouterLink} to="/" variant="contained">
          Go to the dashboard
        </Button>
      }
    />
  );
}

export function AppRoutes() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/course" element={<CoursePage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AppLayout>
  );
}
