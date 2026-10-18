import {
  Button,
  Chip,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import SearchRounded from "@mui/icons-material/SearchRounded";
import type { CourseItem } from "../../api/client";
import { STATUS_LABELS } from "../../components/StatusChip";
import {
  countBy,
  isFiltering,
  toggle,
  typeLabel,
  type Filters,
} from "./filters";

function ChipGroup({
  label,
  options,
  selected,
  name,
  onToggle,
}: {
  label: string;
  options: [string, number][];
  selected: string[];
  name: (value: string) => string;
  onToggle: (value: string) => void;
}) {
  return (
    <Stack
      direction="row"
      spacing={1}
      useFlexGap
      sx={{ flexWrap: "wrap", alignItems: "center" }}
      role="group"
      aria-label={`Filter by ${label.toLowerCase()}`}
    >
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ minWidth: (t) => t.spacing(7) }}
      >
        {label}
      </Typography>
      {options.map(([value, count]) => {
        const on = selected.includes(value);
        return (
          <Chip
            key={value}
            label={`${name(value)} ${count}`}
            onClick={() => onToggle(value)}
            color={on ? "primary" : "default"}
            variant={on ? "filled" : "outlined"}
            aria-pressed={on}
            size="small"
          />
        );
      })}
    </Stack>
  );
}

export function FilterBar({
  items,
  filters,
  onChange,
}: {
  items: CourseItem[];
  filters: Filters;
  onChange: (f: Filters) => void;
}) {
  return (
    <Stack spacing={1.5} role="search" sx={{ mb: 3 }}>
      <TextField
        value={filters.q}
        onChange={(e) => onChange({ ...filters, q: e.target.value })}
        placeholder="Search titles"
        size="small"
        slotProps={{
          htmlInput: { "aria-label": "Search titles" },
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchRounded />
              </InputAdornment>
            ),
          },
        }}
        sx={{ maxWidth: (t) => t.layout.readableWidth }}
      />
      <ChipGroup
        label="Type"
        options={countBy(items, "type")}
        selected={filters.types}
        name={typeLabel}
        onToggle={(v) =>
          onChange({ ...filters, types: toggle(filters.types, v) })
        }
      />
      <ChipGroup
        label="Status"
        options={countBy(items, "status")}
        selected={filters.statuses}
        name={(s) => STATUS_LABELS[s] ?? s}
        onToggle={(v) =>
          onChange({ ...filters, statuses: toggle(filters.statuses, v) })
        }
      />
      {isFiltering(filters) && (
        <Button
          size="small"
          onClick={() => onChange({ q: "", types: [], statuses: [] })}
          sx={{ alignSelf: "flex-start" }}
        >
          Clear filters
        </Button>
      )}
    </Stack>
  );
}
