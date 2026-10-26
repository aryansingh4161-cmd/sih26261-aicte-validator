import { useState } from "react";
import { useView } from "../../data/hooks";
import { currentMode } from "../../data/client";
import { useActions, useDemoActions } from "../../data/actions";
import type { Case, ChecklistRow } from "../../data/types";
import { useT } from "../../app/settings";
import { ErrorState, LaneChip, Skeleton } from "../../components/ui";

// 04 Checklist: one row per requirement, status, what Pramaan found, source, officer action.
const LANE_OF: Record<string, string> = { green: "clear", amber: "human_review", red: "return_for_rectification", grey: "not_automated" };

export function Checklist({ c }: { c: Case }) {
  const t = useT();
  const v = useView<ChecklistRow[]>(`cases/${c.app_id}/checklist`);
  const [only, setOnly] = useState(false);
  const demo = useDemoActions();
  const act = useActions();
  const rows = (v.data || []).filter((r) => !only || r.status === "amber" || r.status === "red");
  return (
    <div className="tabpage">
      <div className="tabpage-head">
        <div><h3>{v.data?.length ?? 14} {t("checks for")} {c.category}</h3></div>
        <div className="toggle-group">
          <button className={"btn small" + (!only ? " on" : "")} aria-pressed={!only} onClick={() => setOnly(false)}>{t("Show all")}</button>
          <button className={"btn small" + (only ? " on" : "")} aria-pressed={only} onClick={() => setOnly(true)}>{t("Only to check / to return")}</button>
        </div>
      </div>
      {v.isLoading && <Skeleton rows={10} height={26} />}
      {v.isError && <ErrorState error={v.error} retry={() => v.refetch()} />}
      {v.data && (
        <table className="table">
          <thead><tr><th>#</th><th>{t("Document")}</th><th>{t("Status")}</th><th>{t("What Pramaan found")}</th><th>{t("Source")}</th><th>{t("Officer")}</th></tr></thead>
          <tbody>
            {rows.map((r) => {
              const fid = r.finding_ids[0];
              const verdict = (currentMode() === "demo" && fid && demo.feedback[fid]) || r.officer;
              return (
                <tr key={r.id}>
                  <td className="muted">{r.n}</td>
                  <td>{r.item}{r.ref && <div className="muted" style={{ fontSize: 12 }}>{r.ref}</div>}</td>
                  <td><LaneChip lane={LANE_OF[r.status]} text={r.status_label} /></td>
                  <td>{r.found}</td>
                  <td>{r.source.includes("(demo adapter)") ? <>{r.source.replace(" (demo adapter)", "")} <span className="tag-demo">{t("demo adapter")}</span></> : r.source}</td>
                  <td>{fid && !verdict ? (
                    <span style={{ display: "flex", gap: 6 }}>
                      <button className="btn small" onClick={() => act.feedback(c.app_id, fid, "correct")}>{t("Correct")}</button>
                      <button className="btn small" onClick={() => act.feedback(c.app_id, fid, "false alarm")}>{t("False alarm")}</button></span>
                  ) : <span className="muted">{verdict ? t(verdict === "correct" ? "Agreed" : "Marked false alarm") : r.status === "grey" ? t("Check by hand") : t("No action needed")}</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
