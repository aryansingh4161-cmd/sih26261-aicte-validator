import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { Icon } from "../icons";
import { ROLES, useSettings } from "../app/settings";
import { LANGUAGES, hasUiTable } from "../i18n";
import { GearMark } from "./ui";

// The Desk frame: icon rail (5 items) + top bar (wordmark, search, theme, language, avatar). DESIGN_SYSTEM.md section 2.
const RAIL = [
  { to: "/", icon: "inbox", label: "My queue" }, { to: "/calendar", icon: "calendar_month", label: "Calendar" },
  { to: "/letters", icon: "description", label: "Letters" }, { to: "/appeals", icon: "history", label: "Appeals" },
  { to: "/analytics", icon: "bar_chart", label: "Analytics" },
];

function useOutside(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) close(); };
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("mousedown", h); document.addEventListener("keydown", k);
    return () => { document.removeEventListener("mousedown", h); document.removeEventListener("keydown", k); };
  }, [open, close]);
  return ref;
}

function LanguageMenu() {
  const { lang, setLang, t } = useSettings();
  const [open, setOpen] = useState(false);
  const ref = useOutside(open, () => setOpen(false));
  const cur = LANGUAGES.find((l) => l.id === lang) || LANGUAGES[0];
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button className="select" aria-haspopup="listbox" aria-expanded={open} aria-label={t("Language")} onClick={() => setOpen(!open)}>
        <Icon name="translate" />{cur.id === "en" ? "English" : cur.native}<Icon name="keyboard_arrow_down" />
      </button>
      {open && (
        <div className="pop" role="listbox" aria-label={t("Language")} style={{ insetInlineEnd: 0, top: 42, width: 240, padding: "6px 0", maxHeight: 420, overflow: "auto" }}>
          {LANGUAGES.map((l) => (
            <button key={l.id} role="option" aria-selected={l.id === lang} className={"menu-item" + (l.id === lang ? " on" : "")}
              onClick={() => { setLang(l.id); setOpen(false); }}>
              <span style={{ minWidth: 80 }}>{l.native}</span><span className="muted" style={{ fontSize: 12.5 }}>{l.name}</span>
            </button>
          ))}
          <p className="note" style={{ padding: "4px 14px 6px", margin: 0 }}>
            {t("Machine-translated (IndicTrans2, offline). The English version is authoritative.")}
          </p>
        </div>
      )}
    </div>
  );
}

function ProfileMenu() {
  const { role, setRole, theme, setTheme, t, signOut } = useSettings();
  const [open, setOpen] = useState(false);
  const ref = useOutside(open, () => setOpen(false));
  const nav = useNavigate();
  const me = ROLES.find((r) => r.id === role) || ROLES[0];
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button className="avatar" aria-haspopup="dialog" aria-expanded={open} aria-label={t("Profile") + ": " + t(me.name)} onClick={() => setOpen(!open)}>
        {me.initials}
      </button>
      {open && (
        <div className="pop" role="dialog" aria-label={t("Who is checking the documents right now?")} style={{ insetInlineEnd: 0, top: 44, width: 340, padding: "16px 0 8px" }}>
          <div style={{ padding: "0 16px 10px" }}>
            <h3 style={{ fontSize: 16 }}>{t("Who is checking the documents right now?")}</h3>
            <p className="muted" style={{ margin: "4px 0 0", fontSize: 13 }}>{t("Choose your role to see your view.")}</p>
          </div>
          {ROLES.map((r) => (
            <button key={r.id} className={"menu-item" + (r.id === role ? " on" : "")} aria-pressed={r.id === role}
              onClick={() => { setRole(r.id); setOpen(false); }}>
              <Icon name={r.id === role ? "check_circle" : "person"} />{t(r.name)}
            </button>
          ))}
          <div style={{ borderTop: "1px solid var(--border)", margin: "8px 0" }} />
          <button className="menu-item" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
            <Icon name={theme === "light" ? "dark_mode" : "light_mode"} />{t("Theme")}: {t(theme === "light" ? "Light" : "Dark")}
          </button>
          <button className="menu-item" onClick={() => { signOut(); nav("/sign-in"); }}><Icon name="logout" />{t("Sign out")}</button>
        </div>
      )}
    </div>
  );
}

function ShortcutSheet({ onClose }: { onClose: () => void }) {
  const { t } = useSettings();
  const rows: [string, string][] = [["j / k", "Next / previous file"], ["Enter", "Open the file"], ["Ctrl K", "Search"], ["?", "This list"], ["Esc", "Close"]];
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-label={t("Keyboard shortcuts")} onClick={(e) => e.stopPropagation()} style={{ width: 420 }}>
        <h3 style={{ marginBottom: 14 }}>{t("Keyboard shortcuts")}</h3>
        <table className="table"><tbody>{rows.map(([k, v]) => <tr key={k}><td><span className="kbd">{k}</span></td><td>{t(v)}</td></tr>)}</tbody></table>
      </div>
    </div>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { theme, setTheme, t, mode } = useSettings();
  const nav = useNavigate();
  const loc = useLocation();
  const input = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState(new URLSearchParams(loc.search).get("q") || "");
  const [help, setHelp] = useState(false);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const typing = /INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); input.current?.focus(); }
      else if (e.key === "?" && !typing) setHelp(true);
      else if (e.key === "Escape") setHelp(false);
    };
    document.addEventListener("keydown", k);
    return () => document.removeEventListener("keydown", k);
  }, []);
  return (
    <div className="app">
      <nav className="rail" aria-label={t("Main")}>
        <div className="logo"><GearMark size={36} /></div>
        {RAIL.map((r) => (
          <NavLink key={r.to} to={r.to} end={r.to === "/"} className={({ isActive }) => (isActive || (r.to === "/" && loc.pathname.startsWith("/case")) ? "active" : "")}>
            <Icon name={r.icon} />{t(r.label)}
          </NavLink>
        ))}
      </nav>
      <header className="topbar">
        <span className="wordmark">Pramaan <b>AI</b></span>
        <form className="search" role="search" onSubmit={(e) => { e.preventDefault(); nav(`/search?q=${encodeURIComponent(q)}`); }}>
          <Icon name="search" className="icon" />
          <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} aria-label={t("Search")}
            placeholder={t("Search Permanent Id, institute, rule or document")} />
          <span className="kbd" aria-hidden="true">Ctrl K</span>
        </form>
        <div className="right">
          {mode === "demo" && <span className="demo-pill" title={t("No server: the 23 synthetic demo files, actions kept in this browser")}>{t("Demo mode: synthetic data")}</span>}
          <button className="iconbtn" aria-label={t(theme === "light" ? "Switch to dark mode" : "Switch to light mode")}
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
            <Icon name={theme === "light" ? "dark_mode" : "light_mode"} />
          </button>
          <LanguageMenu />
          <ProfileMenu />
        </div>
      </header>
      <main className="content" id="main">{children}</main>
      {help && <ShortcutSheet onClose={() => setHelp(false)} />}
    </div>
  );
}

export function LanguageNote() {
  const { lang, mode, t } = useSettings();
  if (lang === "en") return null;
  const dynamicEnglish = mode === "demo" && !["hi", "bn", "ta", "mr"].includes(lang);
  if (hasUiTable(lang) && !dynamicEnglish) return null;
  return <p className="note" role="note">{t("This language is shown in English here: it is translated on the server in the live app.")}</p>;
}
