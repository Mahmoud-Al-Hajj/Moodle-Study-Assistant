import { IconButton, Tooltip, useColorScheme } from "@mui/material";
import DarkModeOutlined from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlined from "@mui/icons-material/LightModeOutlined";

/** Follows the system until clicked; MUI remembers the choice in localStorage. */
export function ColorModeToggle() {
  const { mode, systemMode, setMode } = useColorScheme();
  const dark = (mode === "system" ? systemMode : mode) === "dark";
  const label = dark ? "Switch to light mode" : "Switch to dark mode";
  return (
    <Tooltip title={label}>
      <IconButton
        aria-label={label}
        onClick={() => setMode(dark ? "light" : "dark")}
      >
        {dark ? <LightModeOutlined /> : <DarkModeOutlined />}
      </IconButton>
    </Tooltip>
  );
}
