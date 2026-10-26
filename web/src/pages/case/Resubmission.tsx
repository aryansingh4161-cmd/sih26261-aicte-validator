import { useNavigate } from "react-router-dom";
import { useView } from "../../data/hooks";
import { assetUrl } from "../../data/client";
import type { Case, Resubmission as ResubT } from "../../data/types";
import { useT } from "../../app/settings";
import { Icon } from "../../icons";
import { ErrorState, LaneChip, Skeleton, StateBox } from "../../components/ui";

// 07 Resubmission (resubmit.compare): what changed since the institute's earlier submission.
const LANE = { resolved: "clear", "still open": "human_review", new: "return_for_rectification" } as Record<string, string>;

export function Resubmission({ c }: { c: Case }) {
  const t = useT();
  const nav = useNavigate();
  const v = useView<ResubT>(`cases/${c.app_id}/resubmission`);
  if (v.isLoading) return <div className="tabpage"><Skeleton rows={6} height={26} /></div>;
  if (v.isError || !v.data) return <ErrorState error={v.error} retry={() => v.refetch()} />;
  const d = v.data;
  if (!d.available) return <div className="tabpage"><StateBox icon="history" title={t("No earlier submission")} text={d.note} /></div>;
  const open = d.rows?.find((r) => r.status !== "resolved");
  return (
    <div className="tabpage resub">
      <div>
        <h2 style={{ fontSize: 30 }}>{d.headline}</h2>
        <p className="muted" style={{ margin: "6px 0 16px" }}>{t("The institute resubmitted as")} <span className="mono">{c.app_id}</span> ({t("earlier")}: <span className="mono">{d.previous}</span>). {t("Pramaan re-ran every check. Only what is still open needs you.")}</p>
        <table className="table">
          <thead><tr><th>{t("Issue")}</th><th>{t("Before")}</th><th>{t("After")}</th><th>{t("Result")}</th></tr></thead>
          <tbody>{d.rows?.map((r) => <tr key={r.issue}><td>{r.issue}</td><td>{r.before}</td><td>{r.after}</td><td><LaneChip lane={LANE[r.status]} text={r.result} /></td></tr>)}</tbody>
        </table>
        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          {open && <button className="btn primary" onClick={() => nav(`/case/${c.app_id}`)}>{t("Open the open item")}<Icon name="arrow_forward" /></button>}
          <button className="btn" onClick={() => v.refetch()}><Icon name="refresh" />{t("Re-run all checks")}</button>
        </div>
      </div>
      <div>
        <h3 style={{ fontFamily: "var(--font-body)", fontWeight: 500, fontSize: 15 }}>{d.slot ? d.slot.replace(/_/g, " ") : t("Documents")}</h3>
        <div className="beforeafter">
          <figure><figcaption className="muted">{t("Before")}<span className="sep">·</span><span className="mono">{d.previous}</span></figcaption>
            {d.before_image ? <img src={assetUrl(d.before_image)} alt={t("Before")} /> : <div className="state" style={{ padding: 30 }}>{t("Not submitted")}</div>}</figure>
          <figure><figcaption className="muted">{t("After")}<span className="sep">·</span><span className="mono">{c.app_id}</span></figcaption>
            {d.after_image ? <img src={assetUrl(d.after_image)} alt={t("After")} /> : <div className="state" style={{ padding: 30 }}>{t("Not submitted")}</div>}</figure>
        </div>
        <p className="note">{d.summary}</p>
      </div>
    </div>
  );
}
