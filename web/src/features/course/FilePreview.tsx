import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Divider,
  Drawer,
  IconButton,
  Skeleton,
  Stack,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import CloseRounded from "@mui/icons-material/CloseRounded";
import LaunchRounded from "@mui/icons-material/LaunchRounded";
import FolderOpenOutlined from "@mui/icons-material/FolderOpenOutlined";
import OpenInNewRounded from "@mui/icons-material/OpenInNewRounded";
import VisibilityOffOutlined from "@mui/icons-material/VisibilityOffOutlined";
import { fileUrl, type CourseItem, type ItemFile } from "../../api/client";
import { useFileText, useOpenFile, useRevealFile } from "../../api/queries";
import { useNotify } from "../../components/SnackbarProvider";
import { EmptyState, ErrorState } from "../../components/states";
import { formatBytes } from "../../components/format";

const IMAGE = ["png", "jpg", "jpeg", "gif", "webp", "bmp"];
const VIDEO = ["mp4", "webm", "mov"];
const AUDIO = ["mp3", "m4a", "wav", "ogg"];
const TEXT = ["md", "txt", "csv"];

const inBrowser = (file: ItemFile) =>
  [...IMAGE, ...VIDEO, ...AUDIO, ...TEXT, "pdf"].includes(file.ext);

// Stage 4's flags, in words.
const FLAG_TEXT: Record<string, string> = {
  needs_ocr:
    "This PDF is scanned, so its text can't be read or searched yet (it needs OCR).",
  mostly_images:
    "Most slides are pictures, so the extracted text is short. Open the file to see them.",
  needs_conversion:
    "This old Office file couldn't be converted, so it has no extracted text. Open it in its app.",
  error: "Text extraction failed for this file. Open it in its app instead.",
  unsupported: "This file type isn't supported for text extraction.",
  no_text: "Videos, audio and images have no text to extract.",
};

function TextPreview({ path, label }: { path: string; label?: string }) {
  const text = useFileText(path);
  if (text.isPending)
    return (
      <Box aria-busy="true" aria-label="Loading text">
        {[90, 75, 85, 60].map((w) => (
          <Skeleton key={w} variant="text" width={`${w}%`} />
        ))}
      </Box>
    );
  if (text.isError)
    return <ErrorState error={text.error} onRetry={() => text.refetch()} />;
  return (
    <>
      {label && (
        <Typography variant="overline" color="text.secondary" component="p">
          {label}
        </Typography>
      )}
      <Typography
        component="div"
        variant="body2"
        sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}
      >
        {text.data}
      </Typography>
    </>
  );
}

/** The best in-browser view of one file. Office files show their extracted text. */
function FileBody({ file }: { file: ItemFile }) {
  const src = fileUrl(file.path);
  const frame = { border: 0, width: 1, flex: 1, bgcolor: "background.paper" };
  if (!file.exists)
    return (
      <Alert severity="warning">
        This file isn't on disk anymore. Retry failed (or Download) fetches it
        again.
      </Alert>
    );
  if (file.ext === "pdf")
    return <Box component="iframe" src={src} title={file.name} sx={frame} />;
  if (file.ext === "html" || file.ext === "htm")
    // sandbox: a saved Moodle page runs no script (the API also sends CSP sandbox)
    return (
      <Box
        component="iframe"
        src={src}
        title={file.name}
        sandbox=""
        sx={frame}
      />
    );
  if (IMAGE.includes(file.ext))
    return (
      <Box
        component="img"
        src={src}
        alt={file.name}
        sx={{ maxWidth: 1, height: "auto", alignSelf: "center" }}
      />
    );
  if (VIDEO.includes(file.ext))
    return (
      <Box component="video" src={src} controls sx={{ width: 1 }}>
        {file.name}
      </Box>
    );
  if (AUDIO.includes(file.ext))
    return <Box component="audio" src={src} controls sx={{ width: 1 }} />;
  if (TEXT.includes(file.ext)) return <TextPreview path={file.path} />;
  if (file.text_path)
    return (
      <TextPreview
        path={file.text_path}
        label="Extracted text: open the file for its layout and pictures"
      />
    );
  return (
    <EmptyState
      icon={<VisibilityOffOutlined />}
      title={`No preview for .${file.ext} files`}
      text="Open it in its app or show it in its folder. Running Extract adds a text preview for Office files."
    />
  );
}

/** Side panel previewing an item's files, with open / show in folder / download. */
export function FilePreview({
  item,
  onClose,
}: {
  item: CourseItem | null;
  onClose: () => void;
}) {
  const [tab, setTab] = useState(0);
  const [lastItem, setLastItem] = useState(item?.id);
  const notify = useNotify();
  const open = useOpenFile();
  const reveal = useRevealFile();

  if (item?.id !== lastItem) {
    setLastItem(item?.id); // a different item starts on its first file
    setTab(0);
  }
  const file = item?.files[Math.min(tab, item.files.length - 1)];

  const run = (mutation: typeof open, success: string) =>
    file &&
    mutation.mutate(file.path, {
      onSuccess: () => notify(success, "success"),
      onError: (e) => notify(e.message, "error"),
    });

  return (
    <Drawer
      anchor="right"
      open={item !== null}
      onClose={onClose}
      slotProps={{
        paper: {
          sx: {
            width: { xs: 1, md: (t) => t.layout.previewWidth },
            display: "flex",
            flexDirection: "column",
          },
          "aria-labelledby": "preview-title",
        },
      }}
    >
      {item && file && (
        <>
          <Stack
            direction="row"
            spacing={1}
            sx={{ p: 2, pb: 1, alignItems: "flex-start" }}
          >
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography id="preview-title" variant="h3" component="h2">
                {item.title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {[item.section_name, file.name, formatBytes(file.size)]
                  .filter(Boolean)
                  .join(" · ")}
              </Typography>
            </Box>
            <IconButton onClick={onClose} aria-label="Close preview">
              <CloseRounded />
            </IconButton>
          </Stack>

          {item.files.length > 1 && (
            <Tabs
              value={Math.min(tab, item.files.length - 1)}
              onChange={(_, v: number) => setTab(v)}
              variant="scrollable"
              aria-label="Files of this item"
              sx={{ px: 1 }}
            >
              {item.files.map((f) => (
                <Tab key={f.path} label={f.name} />
              ))}
            </Tabs>
          )}
          <Divider />

          <Stack spacing={2} sx={{ p: 2, flex: 1, overflowY: "auto" }}>
            {file.flags
              .filter((f) => FLAG_TEXT[f])
              .map((f) => (
                <Alert key={f} severity="info">
                  {FLAG_TEXT[f]}
                </Alert>
              ))}
            <FileBody file={file} />
          </Stack>

          {file.exists && (
            <>
              <Divider />
              <Stack
                direction="row"
                spacing={1}
                useFlexGap
                sx={{ p: 2, flexWrap: "wrap" }}
              >
                {file.openable && (
                  <Button
                    variant="contained"
                    startIcon={<LaunchRounded />}
                    onClick={() => run(open, `Opening ${file.name}…`)}
                    disabled={open.isPending}
                  >
                    Open in app
                  </Button>
                )}
                <Button
                  variant="outlined"
                  startIcon={<FolderOpenOutlined />}
                  onClick={() => run(reveal, "Showing it in File Explorer")}
                  disabled={reveal.isPending}
                >
                  Show in folder
                </Button>
                {inBrowser(file) && (
                  <Button
                    startIcon={<OpenInNewRounded />}
                    href={fileUrl(file.path)}
                    target="_blank"
                    rel="noopener"
                  >
                    New tab
                  </Button>
                )}
              </Stack>
            </>
          )}
        </>
      )}
    </Drawer>
  );
}
