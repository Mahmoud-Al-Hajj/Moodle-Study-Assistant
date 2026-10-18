import { createTheme } from "@mui/material/styles";

// The single source of design tokens. Components use palette keys, spacing units and
// theme.layout; never raw colours or pixel sizes.

declare module "@mui/material/styles" {
  interface Theme {
    layout: {
      drawerWidth: number;
      contentMaxWidth: number;
      readableWidth: number;
      logMaxHeight: number;
      illustrationSize: number;
      previewWidth: number;
      statusColumnWidth: number;
      actionsColumnWidth: number;
    };
  }
  interface ThemeOptions {
    layout?: Partial<Theme["layout"]>;
  }
}

const prefersReducedMotion =
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const fontFamily = [
  '"Segoe UI Variable Text"',
  '"Segoe UI"',
  "system-ui",
  "-apple-system",
  '"Helvetica Neue"',
  "Roboto",
  "Arial",
  "sans-serif",
].join(",");

const monoFamily = [
  '"Cascadia Mono"',
  "Consolas",
  "ui-monospace",
  "monospace",
].join(",");

export const theme = createTheme({
  cssVariables: { colorSchemeSelector: "data" },
  colorSchemes: {
    light: {
      palette: {
        primary: { main: "#3f51b5", light: "#e8ebf8", contrastText: "#ffffff" },
        background: { default: "#f6f6f3", paper: "#ffffff" },
        text: { primary: "#1d2026", secondary: "#5a616e" },
        divider: "#e4e4df",
        success: { main: "#2e7d4f" },
        warning: { main: "#b26a00" },
        error: { main: "#c62828" },
        info: { main: "#3f51b5" },
      },
    },
    dark: {
      palette: {
        primary: { main: "#9fa8f0", light: "#262b47", contrastText: "#11131a" },
        background: { default: "#111316", paper: "#191c21" },
        text: { primary: "#e7e9ee", secondary: "#a3a9b5" },
        divider: "#2b2f37",
        success: { main: "#6fcf97" },
        warning: { main: "#f2b453" },
        error: { main: "#f28b82" },
        info: { main: "#9fa8f0" },
      },
    },
  },
  layout: {
    drawerWidth: 248,
    contentMaxWidth: 1080,
    readableWidth: 440,
    logMaxHeight: 280,
    illustrationSize: 44,
    previewWidth: 760,
    statusColumnWidth: 130,
    actionsColumnWidth: 104,
  },
  shape: { borderRadius: 10 },
  spacing: 8,
  typography: {
    fontFamily,
    h1: { fontSize: "2rem", fontWeight: 700, letterSpacing: "-0.02em" },
    h2: { fontSize: "1.5rem", fontWeight: 700, letterSpacing: "-0.01em" },
    h3: { fontSize: "1.125rem", fontWeight: 650 },
    subtitle1: { fontWeight: 600 },
    body1: { lineHeight: 1.6 },
    body2: { lineHeight: 1.55 },
    overline: { fontWeight: 700, letterSpacing: "0.08em" },
    button: { textTransform: "none", fontWeight: 600 },
    caption: { lineHeight: 1.4 },
  },
  transitions: prefersReducedMotion ? { create: () => "none" } : undefined,
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        "@media (prefers-reduced-motion: reduce)": {
          "*, *::before, *::after": {
            animationDuration: "0.01ms !important",
            animationIterationCount: "1 !important",
            transitionDuration: "0.01ms !important",
            scrollBehavior: "auto !important",
          },
        },
        code: { fontFamily: monoFamily },
        pre: { fontFamily: monoFamily },
      },
    },
    MuiButtonBase: {
      defaultProps: { disableRipple: prefersReducedMotion },
      styleOverrides: {
        root: ({ theme }) => ({
          "&.Mui-focusVisible": {
            outline: `2px solid ${theme.vars.palette.primary.main}`,
            outlineOffset: 2,
          },
        }),
      },
    },
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiCard: { defaultProps: { variant: "outlined" } },
    MuiPaper: {
      styleOverrides: {
        outlined: ({ theme }) => ({ borderColor: theme.vars.palette.divider }),
      },
    },
    MuiAppBar: {
      defaultProps: { elevation: 0, color: "inherit" },
      styleOverrides: {
        root: ({ theme }) => ({
          backgroundColor: theme.vars.palette.background.paper,
          borderBottom: `1px solid ${theme.vars.palette.divider}`,
        }),
      },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiLinearProgress: {
      styleOverrides: {
        root: ({ theme }) => ({
          borderRadius: theme.shape.borderRadius,
          height: 6,
        }),
      },
    },
    MuiTooltip: { defaultProps: { arrow: true } },
  },
});

export { monoFamily };
