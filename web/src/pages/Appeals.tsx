import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useView } from "../data/hooks";
import type { Appeals as AppealsT } from "../data/types";
import { useSettings } from "../app/settings";
import { ErrorState, LaneChip, Skeleton, StateBox } from "../components/ui";

// 11 Appeals tracker (appeal.py): Standing Appellate Committee, 7-day window bars.
export function Appeals() {
  const { t } = useSettings();
  const nav = useNavigate();
  const v = useView<AppealsT>("appeals");
  const [tab, setTab] = useState("open");
  const all = v.data?.appeals || [];
  const rows = tab === "all" ? all : tab === "open" ? all.filter((a) => a.state === "open") : all.filter((a) => a.state !== "open");
  return (
    <div className="page">
      <div className="page-head"><div><span className="eyebrow">{t("Standing Appellate Committee")}<span className="sep">·</span>{t("All regions")}</span>
        <h1>{t("Appeals.")}<span className="line2">{v.data ? v.data.headline : " "}</span></h1></div></div>
      <div className="subtabs" role="tablist">
        {[["open", "Open"], ["decided", "Decided"], ["all", "All"]].map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{t(l)}
            {k !== "all" && <span className="muted"> {k === "open" ? all.filter((a) => a.state === "open").length : all.filter((a) => a.state !== "open").length}</span>}</button>))}
      </div>
      {v.isLoading && <Skeleton rows={5} height={26} />}
      {v.isError && <ErrorState error={v.error} retry={() => v.refetch()} />}
      {v.data && !rows.length && <StateBox icon="history" title={t("No appeals here.")} text={t("An appeal window opens when a Letter of Deficiency is sealed and issued.")} />}
      {rows.length > 0 && (
        <table className="table">
          <thead><tr><th>{t("Appeal")}</th><th>{t("Institute")}</th><th>{t("Against")}</th><th>{t("Filed")}</th><th>{t("Appeal window")}</th><th>{t("Status")}</th></tr></thead>
          <tbody>{rows.map((a) => {
            const used = 7 - a.days_left;
            return (
              <tr key={a.appeal} className="clickable" onClick={() => nav(`/case/${a.app_id}`)}>
                <td className="mono">{a.appeal}</td><td>{a.institute}</td><td><span className="chip plain">{a.against}</span></td>
                <td>{new Date(a.filed).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</td>
                <td><span className="window"><span className="track"><span className={a.state !== "open" || a.days_left <= 1 ? "ret" : "rev"} style={{ width: `${(a.state === "open" ? used / 7 : 1) * 100}%` }} /></span>
                  <span className={a.state !== "open" || a.days_left <= 1 ? "t-ret" : ""}>{a.state === "open" ? `${a.days_left} ${t("of")} 7 ${t("days left")}` : t("closed")}</span></span></td>
                <td><LaneChip lane={a.state === "open" ? "human_review" : "not_automated"} text={a.state_label} /></td>
              </tr>);
          })}</tbody>
        </table>
      )}
      <p className="note">{v.data?.note}</p>
    </div>
  );
}
