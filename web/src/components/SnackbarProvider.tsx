import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { Alert, Snackbar, type AlertColor } from "@mui/material";

type Notify = (message: string, severity?: AlertColor) => void;
const Ctx = createContext<Notify>(() => {});

/** Short confirmations and errors at the bottom of the screen. */
export function SnackbarProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<{
    text: string;
    severity: AlertColor;
    key: number;
  } | null>(null);
  const notify = useCallback<Notify>(
    (text, severity = "info") => setMsg({ text, severity, key: Date.now() }),
    [],
  );
  return (
    <Ctx.Provider value={notify}>
      {children}
      <Snackbar
        key={msg?.key}
        open={msg !== null}
        autoHideDuration={msg?.severity === "error" ? 8000 : 4000}
        onClose={(_, reason) => reason !== "clickaway" && setMsg(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          severity={msg?.severity ?? "info"}
          variant="filled"
          onClose={() => setMsg(null)}
          sx={{ width: "100%" }}
        >
          {msg?.text}
        </Alert>
      </Snackbar>
    </Ctx.Provider>
  );
}

export const useNotify = () => useContext(Ctx);
