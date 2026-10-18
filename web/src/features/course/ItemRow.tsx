import {
  Box,
  IconButton,
  Link,
  Stack,
  TableCell,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import VisibilityOutlined from "@mui/icons-material/VisibilityOutlined";
import OpenInNewRounded from "@mui/icons-material/OpenInNewRounded";
import type { CourseItem } from "../../api/client";
import { StatusChip } from "../../components/StatusChip";
import { ItemIcon } from "./ItemIcon";

const hostname = (url: string) => {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
};

export const previewable = (item: CourseItem) =>
  item.files.some((f) => f.exists);

/** One course item: type icon, title (opens the preview, or the link), note, status, actions. */
export function ItemRow({
  item,
  onPreview,
}: {
  item: CourseItem;
  onPreview: (item: CourseItem) => void;
}) {
  const canPreview = previewable(item);
  const link = item.type === "url" ? item.target_url : "";
  const fileCount = item.files.length;

  return (
    <TableRow hover>
      <TableCell padding="checkbox" sx={{ pl: 2 }}>
        <ItemIcon item={item} />
      </TableCell>
      <TableCell sx={{ minWidth: 0, wordBreak: "break-word" }}>
        {canPreview ? (
          <Link
            component="button"
            variant="body2"
            onClick={() => onPreview(item)}
            sx={{ textAlign: "start", fontWeight: 600 }}
          >
            {item.title}
          </Link>
        ) : link ? (
          <Link
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            variant="body2"
            sx={{ fontWeight: 600 }}
          >
            {item.title}
          </Link>
        ) : (
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {item.title}
          </Typography>
        )}
        {(link || item.note || fileCount > 1) && (
          <Typography
            variant="caption"
            component="p"
            color={item.status === "failed" ? "error" : "text.secondary"}
            title={item.note || undefined}
            sx={{
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              wordBreak: "break-all",
            }}
          >
            {[
              link && hostname(link),
              fileCount > 1 && `${fileCount} files`,
              item.note,
            ]
              .filter(Boolean)
              .join(" · ")}
          </Typography>
        )}
        <Box sx={{ display: { sm: "none" }, mt: 0.5 }}>
          <StatusChip status={item.status} />
        </Box>
      </TableCell>
      <TableCell sx={{ display: { xs: "none", sm: "table-cell" } }}>
        <StatusChip status={item.status} />
      </TableCell>
      <TableCell align="right" sx={{ whiteSpace: "nowrap", pr: 1 }}>
        <Stack direction="row" justifyContent="flex-end">
          {canPreview && (
            <Tooltip title="Preview">
              <IconButton
                onClick={() => onPreview(item)}
                aria-label={`Preview ${item.title}`}
              >
                <VisibilityOutlined />
              </IconButton>
            </Tooltip>
          )}
          {item.url && (
            <Tooltip title="Open in Moodle">
              <IconButton
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open ${item.title} in Moodle`}
              >
                <OpenInNewRounded />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
      </TableCell>
    </TableRow>
  );
}
