import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { applyLanguage, translate } from "../i18n";
import { currentMode, detectMode, type Mode } from "../data/client";

// Theme, language, role and data mode for the whole app. Theme / language / role are remembered in this browser.
export const ROLES = [
  { id: "regulation_bureau", name: "Regulation Bureau", initials: "RB" },
  { id: "scrutiny", name: "Scrutiny / Re-Scrutiny Committee", initials: "SC" },
  { id: "evc", name: "Expert Visit Committee", initials: "EV" },
  { id: "shc", name: "Standing Hearing Committee", initials: "SH" },
  { id: "ec", name: "Executive Committee", initials: "EC" },
  { id: "sac", name: "Standing Appellate Committee", initials: "SA" },
];
type Settings = {
  theme: "light" | "dark"; setTheme: (t: "light" | "dark") => void;
  lang: string; setLang: (l: string) => void;
  role: string; setRole: (r: string) => void;
  mode: Mode; signedIn: boolean; signIn: () => void; signOut: () => void;
  t: (text: string) => string;
};
const Ctx = createContext<Settings | null>(null);

function remembered<T extends string>(key: string, fallback: T): T {
  try { return (localStorage.getItem(key) as T) || fallback; } catch { return fallback; }
}
function remember(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* storage blocked: the choice lasts for this page only */ }
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeS] = useState<"light" | "dark">(() => remembered("pramaan.theme", "light"));
  const [lang, setLangS] = useState<string>(() => remembered<string>("pramaan.lang", "en"));
  const [role, setRoleS] = useState<string>(() => remembered<string>("pramaan.role", "regulation_bureau"));
  const [signedIn, setSignedIn] = useState(() => remembered<string>("pramaan.signedIn", "") === "yes");
  const [mode, setMode] = useState<Mode>(currentMode());

  useEffect(() => { document.documentElement.dataset.theme = theme; remember("pramaan.theme", theme); }, [theme]);
  useEffect(() => { applyLanguage(lang); remember("pramaan.lang", lang); }, [lang]);
  useEffect(() => { remember("pramaan.role", role); }, [role]);
  useEffect(() => { detectMode().then(setMode); }, []);

  const t = useCallback((text: string) => translate(lang, text), [lang]);
  const value = useMemo<Settings>(() => ({
    theme, setTheme: setThemeS, lang, setLang: setLangS, role, setRole: setRoleS, mode, signedIn,
    signIn: () => { setSignedIn(true); remember("pramaan.signedIn", "yes"); },
    signOut: () => { setSignedIn(false); remember("pramaan.signedIn", ""); },
    t,
  }), [theme, lang, role, mode, signedIn, t]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSettings(): Settings {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSettings outside SettingsProvider");
  return s;
}
export const useT = () => useSettings().t;
