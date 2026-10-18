import type { SvgIconComponent } from "@mui/icons-material";
import InsertDriveFileOutlined from "@mui/icons-material/InsertDriveFileOutlined";
import PictureAsPdfOutlined from "@mui/icons-material/PictureAsPdfOutlined";
import SlideshowOutlined from "@mui/icons-material/SlideshowOutlined";
import DescriptionOutlined from "@mui/icons-material/DescriptionOutlined";
import MovieOutlined from "@mui/icons-material/MovieOutlined";
import ImageOutlined from "@mui/icons-material/ImageOutlined";
import FolderOutlined from "@mui/icons-material/FolderOutlined";
import ArticleOutlined from "@mui/icons-material/ArticleOutlined";
import LinkRounded from "@mui/icons-material/LinkRounded";
import AssignmentOutlined from "@mui/icons-material/AssignmentOutlined";
import ForumOutlined from "@mui/icons-material/ForumOutlined";
import QuizOutlined from "@mui/icons-material/QuizOutlined";
import ExtensionOutlined from "@mui/icons-material/ExtensionOutlined";
import type { CourseItem } from "../../api/client";
import { typeLabel } from "./filters";

const BY_EXT: Record<string, SvgIconComponent> = {
  pdf: PictureAsPdfOutlined,
  ppt: SlideshowOutlined,
  pptx: SlideshowOutlined,
  pps: SlideshowOutlined,
  ppsx: SlideshowOutlined,
  doc: DescriptionOutlined,
  docx: DescriptionOutlined,
  md: DescriptionOutlined,
  txt: DescriptionOutlined,
  mp4: MovieOutlined,
  webm: MovieOutlined,
  mov: MovieOutlined,
  png: ImageOutlined,
  jpg: ImageOutlined,
  jpeg: ImageOutlined,
  gif: ImageOutlined,
  webp: ImageOutlined,
};

const BY_MODULE: Record<string, SvgIconComponent> = {
  folder: FolderOutlined,
  page: ArticleOutlined,
  url: LinkRounded,
  assign: AssignmentOutlined,
  forum: ForumOutlined,
  quiz: QuizOutlined,
};

/** Type icon: by file extension for files, by Moodle module otherwise. */
export function ItemIcon({ item }: { item: CourseItem }) {
  const ext = item.files[0]?.ext ?? "";
  const Icon =
    BY_MODULE[item.module] ??
    BY_EXT[ext] ??
    (item.type === "resource" || item.module === "inline_file"
      ? InsertDriveFileOutlined
      : ExtensionOutlined);
  const label =
    item.type === "other" && item.module
      ? item.module[0].toUpperCase() + item.module.slice(1).replace("_", " ")
      : typeLabel(item.type);
  return (
    <Icon
      color="action"
      titleAccess={ext ? `${label} (${ext})` : label}
      fontSize="small"
    />
  );
}
