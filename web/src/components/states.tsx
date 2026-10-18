import type { ReactNode } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Skeleton,
  Stack,
  Typography,
} from "@mui/material";
import RefreshRounded from "@mui/icons-material/RefreshRounded";

/** Nothing here yet, with the next step to take. */
export function EmptyState({
  icon,
  title,
  text,
  action,
}: {
  icon?: ReactNode;
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <Stack
      alignItems="center"
      spacing={1.5}
      sx={{ py: 5, px: 2, textAlign: "center" }}
    >
      {icon && (
        <Box
          sx={{
            color: "text.secondary",
            "& svg": { fontSize: (t) => t.layout.illustrationSize },
          }}
        >
          {icon}
        </Box>
      )}
      <Typography variant="h3" component="p">
        {title}
      </Typography>
      <Typography
        color="text.secondary"
        sx={{ maxWidth: (t) => t.layout.readableWidth }}
      >
        {text}
      </Typography>
      {action}
    </Stack>
  );
}

/** A friendly error with a retry button. Messages come from ApiError, never stack traces. */
export function ErrorState({
  error,
  onRetry,
}: {
  error: Error;
  onRetry?: () => void;
}) {
  return (
    <Alert
      severity="error"
      action={
        onRetry && (
          <Button
            color="inherit"
            size="small"
            startIcon={<RefreshRounded />}
            onClick={onRetry}
          >
            Retry
          </Button>
        )
      }
    >
      {error.message}
    </Alert>
  );
}

/** Placeholder while a card's data loads. */
export function LoadingCard({ lines = 3 }: { lines?: number }) {
  return (
    <Card aria-busy="true" aria-label="Loading">
      <CardContent>
        <Skeleton variant="text" width="40%" sx={{ fontSize: "1.25rem" }} />
        {Array.from({ length: lines }, (_, i) => (
          <Skeleton key={i} variant="text" width={`${85 - i * 15}%`} />
        ))}
      </CardContent>
    </Card>
  );
}
