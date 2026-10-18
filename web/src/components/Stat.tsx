import { Box, Typography } from "@mui/material";

type Tone = "default" | "success" | "error" | "warning";

/** One labelled number, e.g. "62 Downloaded". */
export function Stat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: number;
  tone?: Tone;
}) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography
        variant="h2"
        component="p"
        sx={{
          color:
            tone === "default" || value === 0 ? "text.primary" : `${tone}.main`,
        }}
      >
        {value.toLocaleString()}
      </Typography>
      <Typography variant="body2" color="text.secondary" noWrap>
        {label}
      </Typography>
    </Box>
  );
}
