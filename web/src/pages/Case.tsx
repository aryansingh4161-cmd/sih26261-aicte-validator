import { NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useState } from "react";
import { useView } from "../data/hooks";
import { caseZipUrl, currentMode } from "../data/client";
import { useDemoActions, useTicks, useVerdicts } from "../data/actions";
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

/** Quiet guidance (WK27 D1): what is still open, and the one next step. Copy only; the counts come from the case view. */
function useGuidance(c: CaseT) {
  const { t } = useSettings();
  const verdict = useVerdicts(c.findings);
  const ticked = useTicks(c.app_id, c.findings);
  const open = c.findings.filter((f) => (f.lane === "return_for_rectification" || f.lane === "human_review") && !verdict(f.finding_id)).length;
  const inLetter = c.findings.filter((f) => (f.lane === "return_for_rectification" || f.lane === "human_review")
    && ticked(f.finding_id, f.lane === "return_for_rectification")).length;
  const sealed = c.timeline.some((e) => e.type === "letter issued");
  const next = open ? `${t("Next")}: ${(open === 1 ? t("confirm 1 finding") : t("confirm {n} findings").replace("{n}", String(open)))}${inLetter || c.lane !== "clear" ? ", " + t("then draft the letter") : ""}`
    : sealed ? `${t("Next")}: ${t("wait for the institute's reply or an appeal")}`
    : inLetter ? `${t("Next")}: ${t("draft the Letter of Deficiency")} (${inLetter})`
    : c.lane === "clear" ? `${t("Next")}: ${t("approve it with the clear files after the spot check")}`
    : `${t("Next")}: ${t("no deficiency is confirmed; record the result")}`;
  const ck = c.checklist.to_return ? `${c.checklist.to_return} ${t("to return")}` : c.checklist.to_check ? `${c.checklist.to_check} ${t("to check")}` : "";
  return { open, next, ck };
}

function CaseFrame({ c }: { c: CaseT }) {
  const { t, role } = useSettings();
  const nav = useNavigate();
  const demo = useDemoActions();
  const g = useGuidance(c);
  const [assign, setAssign] = useState(false);
  const notes = c.notes_count + (currentMode() === "demo" ? (demo.notes[c.app_id] || []).length : 0);
  const officers = useView<{ id: string; name: string }[]>("officers");
  const mine = currentMode() === "demo" && demo.assigned[c.app_id];
  const assigned = (mine && (officers.data?.find((o) => o.id === mine)?.name || mine)) || c.assigned;
  return (
    <div className="casepage">
      <div className="casehead">
        <nav className="crumbs" aria-label={t("Breadcrumb")}><a href={`#/?file=${c.app_id}`} className="back"><Icon name="arrow_back" />{t("My queue")}</a>
          <Icon name="chevron_right" /><span>{c.app_id}</span></nav>
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
            <a className="btn" href={caseZipUrl(c.app_id)} download={`${c.app_id}_case.zip`} title={t("Officer copy of the case file: documents, findings, audit slice")}>
              <Icon name="download" />{t("Case ZIP")}</a>
            <button className="btn primary" onClick={() => nav(role === "regulation_bureau" ? `/case/${c.app_id}/letter` : mainActionPath(role, c.app_id, c.lane))}>{c.action}<Icon name="arrow_forward" /></button>
          </div>
        </div>
        <div className="strip" style={{ marginTop: 12 }}>
          <LaneChip lane={c.lane} text={c.lane_label} /><TrustBar score={c.trust.score} /><ChecklistCounts c={c.checklist} />
          <span className="muted">{t("Assigned to")} {assigned}<span className="sep">·</span>{t("Due")} {c.due_word}</span>
        </div>
        <p className="nextline">{g.next}</p>
      </div>
      <nav className="tabband" aria-label={t("Case sections")}>
        {TABS.map(([to, label]) => (
          <NavLink key={to} to={`/case/${c.app_id}${to ? "/" + to : ""}`} end className={({ isActive }) => (isActive ? "on" : "")}>
            {t(label)}{to === "" && g.open > 0 && <span className="tabcount"> · {g.open} {t("to check")}</span>}
            {to === "checklist" && g.ck && <span className="tabcount"> · {g.ck}</span>}
            {to === "notes" && notes > 0 && <span className="tabcount"> · {notes}</span>}
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
