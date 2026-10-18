import { useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router";
import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  Link,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import MenuRounded from "@mui/icons-material/MenuRounded";
import SpaceDashboardOutlined from "@mui/icons-material/SpaceDashboardOutlined";
import FolderOpenOutlined from "@mui/icons-material/FolderOpenOutlined";
import SearchRounded from "@mui/icons-material/SearchRounded";
import MenuBookOutlined from "@mui/icons-material/MenuBookOutlined";
import StyleOutlined from "@mui/icons-material/StyleOutlined";
import QuizOutlined from "@mui/icons-material/QuizOutlined";
import SettingsOutlined from "@mui/icons-material/SettingsOutlined";
import SchoolOutlined from "@mui/icons-material/SchoolOutlined";
import { ColorModeToggle } from "../theme/ColorModeToggle";

/** Every screen; `stage` marks the ones not built yet (shown disabled). */
export const NAV = [
  { to: "/", label: "Dashboard", icon: <SpaceDashboardOutlined /> },
  {
    to: "/course",
    label: "Course content",
    icon: <FolderOpenOutlined />,
    stage: "B",
  },
  { to: "/search", label: "Search", icon: <SearchRounded />, stage: "D" },
  { to: "/reader", label: "Reader", icon: <MenuBookOutlined />, stage: "D" },
  {
    to: "/flashcards",
    label: "Flashcards",
    icon: <StyleOutlined />,
    stage: "E",
  },
  { to: "/quiz", label: "Quiz", icon: <QuizOutlined />, stage: "E" },
  {
    to: "/settings",
    label: "Settings",
    icon: <SettingsOutlined />,
    stage: "F",
  },
];

function Brand() {
  return (
    <Stack
      direction="row"
      spacing={1.25}
      alignItems="center"
      sx={{ minWidth: 0 }}
    >
      <SchoolOutlined color="primary" />
      <Typography variant="subtitle1" component="span" noWrap>
        Study Assistant
      </Typography>
    </Stack>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const { pathname } = useLocation();
  return (
    <Box component="nav" aria-label="Main">
      <List sx={{ px: 1 }}>
        {NAV.map((item) => (
          <ListItemButton
            key={item.to}
            component={NavLink}
            to={item.to}
            onClick={onNavigate}
            disabled={Boolean(item.stage)}
            selected={!item.stage && pathname === item.to}
            aria-current={pathname === item.to ? "page" : undefined}
            sx={{ borderRadius: 1, mb: 0.5 }}
          >
            <ListItemIcon sx={{ minWidth: (t) => t.spacing(5) }}>
              {item.icon}
            </ListItemIcon>
            <ListItemText
              primary={item.label}
              secondary={
                item.stage ? `Coming in stage ${item.stage}` : undefined
              }
              slotProps={{ secondary: { variant: "caption" } }}
            />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
}

/** Sidebar on desktop; top bar with a drawer on small screens. */
export function AppLayout({ children }: { children: ReactNode }) {
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up("md"));
  const [open, setOpen] = useState(false);
  const width = theme.layout.drawerWidth;

  return (
    <Box
      sx={{
        display: "flex",
        minHeight: "100vh",
        bgcolor: "background.default",
      }}
    >
      <Link
        href="#main"
        sx={{
          position: "absolute",
          left: (t) => t.spacing(-200),
          zIndex: (t) => t.zIndex.tooltip,
          "&:focus": {
            left: (t) => t.spacing(2),
            top: (t) => t.spacing(2),
            p: 1,
            bgcolor: "background.paper",
          },
        }}
      >
        Skip to content
      </Link>

      {!desktop && (
        <AppBar position="fixed">
          <Toolbar>
            <IconButton
              edge="start"
              aria-label="Open navigation"
              onClick={() => setOpen(true)}
              sx={{ mr: 1 }}
            >
              <MenuRounded />
            </IconButton>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Brand />
            </Box>
            <ColorModeToggle />
          </Toolbar>
        </AppBar>
      )}

      <Drawer
        variant={desktop ? "permanent" : "temporary"}
        open={desktop || open}
        onClose={() => setOpen(false)}
        sx={{
          width,
          flexShrink: 0,
          "& .MuiDrawer-paper": { width, boxSizing: "border-box" },
        }}
      >
        <Toolbar sx={{ justifyContent: "space-between" }}>
          <Brand />
          {desktop && <ColorModeToggle />}
        </Toolbar>
        <NavList onNavigate={() => setOpen(false)} />
      </Drawer>

      <Box
        component="main"
        id="main"
        tabIndex={-1}
        sx={{
          flex: 1,
          minWidth: 0,
          px: { xs: 2, sm: 3, md: 5 },
          py: { xs: 3, md: 5 },
          outline: "none",
        }}
      >
        {!desktop && <Toolbar />}
        <Box sx={{ maxWidth: (t) => t.layout.contentMaxWidth, mx: "auto" }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}
