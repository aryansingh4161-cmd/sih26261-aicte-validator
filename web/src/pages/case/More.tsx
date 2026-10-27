import { useNavigate } from "react-router-dom";
import { currentMode } from "../../data/client";
import { useDemoActions } from "../../data/actions";
import type { Case } from "../../data/types";
import { useT } from "../../app/settings";
import { Icon } from "../../icons";
import { ChainTimeline, STEP_LABEL } from "../../components/case";
import { NotesList } from "./Evidence";

// Case tabs: Letters (this file's letters), Notes (internal, never sent), Timeline (the audit chain).
export function CaseLetters({ c }: { c: Case }) {
  const t = useT();
  const nav = useNavigate();
  const demo = useDemoActions();
  const issued = c.timeline.filter((e) => e.type === "letter issued");
  const local = currentMode() === "demo" ? demo.sealed[c.app_id] : undefined;
  return (
    <div className="tabpage" style={{ maxWidth: 820 }}>
      <table className="table">
        <thead><tr><th>{t("Letter")}</th><th>{t("Status")}</th><th>{t("Seal hash")}</th><th>{t("Date")}</th></tr></thead>
        <tbody>
          {issued.map((e) => <tr key={e.ts}><td>{t("Letter of Deficiency")}</td><td><span className="chip na"><Icon name="verified_user" />{t("Sealed")}</span></td>
            <td className="mono">#{e.hash.slice(0, 6)}</td><td>{new Date(e.ts).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</td></tr>)}
          {local && <tr><td>{t("Letter of Deficiency")}</td><td><span className="chip na"><Icon name="verified_user" />{t("Sealed in this browser (demo)")}</span></td>
            <td className="mono">#{local.hash.slice(0, 6)}</td><td>{new Date(local.ts).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</td></tr>}
          {!issued.length && !local && <tr><td>{t("Letter of Deficiency")}</td><td><span className="chip rev"><Icon name="visibility" />{t("Draft")}</span></td>
            <td className="mono muted">{t("not sealed")}</td><td /></tr>}
        </tbody>
      </table>
      <button className="btn primary" style={{ marginTop: 16 }} onClick={() => nav(`/case/${c.app_id}/letter`)}>{t("Open the letter editor")}<Icon name="arrow_forward" /></button>
    </div>
  );
}

export function Notes({ c }: { c: Case }) {
  const t = useT();
  return (
    <div className="tabpage" style={{ maxWidth: 640 }}>
      <p className="muted" style={{ marginTop: 0 }}>{t("Internal notes between officers. They are never part of a letter or the institute's copy of the case file.")}</p>
      <NotesList appId={c.app_id} />
    </div>
  );
}

export function Timeline({ c }: { c: Case }) {
  const t = useT();
  return (
    <div className="tabpage">
      <p className="muted" style={{ marginTop: 0 }}>{t("Every step is a block in the audit chain. Each hash depends on the block before it, so a changed step shows.")}</p>
      <ChainTimeline events={c.timeline} lane={c.lane} />
      <table className="table" style={{ marginTop: 20 }}>
        <thead><tr><th>{t("When")}</th><th>{t("Step")}</th><th>{t("By")}</th><th>{t("Hash")}</th><th>{t("Note")}</th></tr></thead>
        <tbody>{c.timeline.map((e) => <tr key={e.type + e.ts}><td className="muted">{e.ts.replace("T", " ").slice(0, 16)}</td><td>{t(STEP_LABEL[e.type] || e.type)}</td>
          <td>{e.actor}</td><td className="mono">{e.real ? "#" + e.hash : ""}</td><td className="muted">{e.note}</td></tr>)}</tbody>
      </table>
    </div>
  );
}
