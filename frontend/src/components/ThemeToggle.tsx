// Theme button: cycles system → light → dark. "system" means no data-theme, so the OS preference applies.
import { useState } from "react";

type Theme = "system" | "light" | "dark";
const KEY = "fjg.theme";
const NEXT: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
const ICON: Record<Theme, string> = { system: "◐", light: "☀", dark: "☾" };

function stored(): Theme {
  try {
    const t = localStorage.getItem(KEY);
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

function apply(t: Theme) {
  if (t === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = t;
  try {
    if (t === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, t);
  } catch {
    /* ignore */
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(stored);
  const next = NEXT[theme];
  return (
    <button
      type="button"
      title={`Theme: ${theme} (click for ${next})`}
      aria-label={`Theme: ${theme}. Switch to ${next}`}
      onClick={() => {
        apply(next);
        setTheme(next);
      }}
      className="h-9 rounded-ui border border-border px-3 hover:bg-surface"
    >
      {ICON[theme]}
    </button>
  );
}
