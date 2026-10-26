import { NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useState } from "react";
import { useView } from "../data/hooks";
import { currentMode } from "../data/client";
import { useDemoActions } from "../data/actions";
import type { Case as CaseT } from "../data/types";
import { mainActionPath, useSettings } from "../app/settings";
import { Icon } from "../icons";
import { ErrorState, LaneChip, LoadingTable } from "../components/ui";
import { ChecklistCounts, TrustBar } from "../components/case";
import { AssignMenu } from "./Home";
import { Evidence } from "./case/Evidence";
import { Checklist } from "./case/Checklist";
import { Sources } from "./case/Sources";
import { Changes } from "./case/Changes";
import { Resubmission } from "./case/Resubmission";
import { CaseLetters, Notes, Timeline } from "./case/More";
import { LetterEditor } from "./LetterEditor";

// 03-07 Case pages: case header + summary strip, then the TAB BAND on its own darker band (DESIGN_SYSTEM.md section 2).
const TABS: [string, string][] = [["", "Evidence"], ["checklist", "Checklist"], ["sources", "Verification sources"], ["changes", "Changes since 2025"],
  ["resubmission", "Resubmission"], ["letters", "Letters"], ["notes", "Notes"], ["timeline", "Timeline"]];

export function CasePage() {
  const { id = "" } = useParams();
  const c = useView<CaseT>(`cases/${id}`);
  if (c.isLoading) return <LoadingTable what={id} />;
  if (c.isError || !c.data) return <ErrorState error={c.error} retry={() => c.refetch()} />;
  return (
    <Routes>
      <Route path="letter" element={<LetterEditor c={c.data} />} />
      <Route path="*" element={<CaseFrame c={c.data} />} />
    </Routes>
  );
}

function CaseFrame({ c }: { c: CaseT }) {
  const { t, mode, role } = useSettings();
  const nav = useNavigate();
  const demo = useDemoActions();
  const [assign, setAssign] = useState(false);
  const notes = c.notes_count + (currentMode() === "demo" ? (demo.notes[c.app_id] || []).length : 0);
  const assigned = (currentMode() === "demo" && demo.assigned[c.app_id]) || c.assigned;
  return (
    <div className="casepage">
      <div className="casehead">
        <nav className="crumbs" aria-label={t("Breadcrumb")}><a href="#/">{t("My queue")}</a><Icon name="chevron_right" /><span>{c.app_id}</span></nav>
        <div className="casehead-row">
          <div>
            <h1 className="case-title">{c.institute}</h1>
            <div className="meta" style={{ fontSize: 13.5 }}><span className="mono">{c.app_id}</span><span className="sep">·</span>{t("Permanent Id")} <span className="mono">{c.permanent_id}</span>
              <span className="sep">·</span>{c.category} {c.academic_year}<span className="sep">·</span>{c.place}</div>
          </div>
          <div className="actions" style={{ display: "flex", gap: 8 }}>
            <div style={{ position: "relative" }}>
              <button className="btn" onClick={() => setAssign(!assign)} aria-expanded={assign}>{t("Assign")}</button>
              {assign && <AssignMenu appId={c.app_id} onClose={() => setAssign(false)} />}
            </div>
            {mode === "live" ? <a className="btn" href={`/api/cases/${c.app_id}/zip`} download><Icon name="download" />{t("Case ZIP")}</a>
              : <button className="btn" disabled title={t("The case ZIP is built by the server in the live app.")}><Icon name="download" />{t("Case ZIP")}</button>}
            <button className="btn primary" onClick={() => nav(role === "regulation_bureau" ? `/case/${c.app_id}/letter` : mainActionPath(role, c.app_id, c.lane))}>{c.action}<Icon name="arrow_forward" /></button>
          </div>
        </div>
        <div className="strip" style={{ marginTop: 12 }}>
          <LaneChip lane={c.lane} text={c.lane_label} /><TrustBar score={c.trust.score} /><ChecklistCounts c={c.checklist} />
          <span className="muted">{t("Assigned to")} {assigned}<span className="sep">·</span>{t("Due")} {c.due_word}</span>
        </div>
      </div>
      <nav className="tabband" aria-label={t("Case sections")}>
        {TABS.map(([to, label]) => (
          <NavLink key={to} to={`/case/${c.app_id}${to ? "/" + to : ""}`} end className={({ isActive }) => (isActive ? "on" : "")}>
            {t(label)}{to === "notes" && notes > 0 && <span className="muted"> {notes}</span>}
          </NavLink>
        ))}
      </nav>
      <div className="casebody">
        <Routes>
          <Route index element={<Evidence c={c} />} />
          <Route path="checklist" element={<Checklist c={c} />} />
          <Route path="sources" element={<Sources c={c} />} />
          <Route path="changes" element={<Changes c={c} />} />
          <Route path="resubmission" element={<Resubmission c={c} />} />
          <Route path="letters" element={<CaseLetters c={c} />} />
          <Route path="notes" element={<Notes c={c} />} />
          <Route path="timeline" element={<Timeline c={c} />} />
        </Routes>
      </div>
    </div>
  );
}
