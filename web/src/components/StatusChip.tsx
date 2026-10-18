import { Chip, type ChipProps } from "@mui/material";

type Tone = NonNullable<ChipProps["color"]>;

// Every status the UI shows, from the session, the manifest and jobs.
const STATUS: Record<string, [string, Tone]> = {
  valid: ["Logged in", "success"],
  expired: ["Session expired", "warning"],
  missing: ["Not logged in", "warning"],
  unknown: ["Not checked", "default"],
  running: ["Running", "info"],
  succeeded: ["Done", "success"],
  failed: ["Failed", "error"],
  session_expired: ["Session expired", "warning"],
  cancelled: ["Cancelled", "default"],
  pending: ["Pending", "default"],
  downloaded: ["Downloaded", "success"],
  unavailable: ["Unavailable", "default"],
  skipped: ["Skipped", "default"],
};

export function StatusChip({
  status,
  size = "small",
}: {
  status: string;
  size?: ChipProps["size"];
}) {
  const [label, color] = STATUS[status] ?? [status, "default"];
  return (
    <Chip
      size={size}
      label={label}
      color={color}
      variant={color === "default" ? "outlined" : "filled"}
    />
  );
}
