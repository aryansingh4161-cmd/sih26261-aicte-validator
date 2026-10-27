import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useView } from "../../data/hooks";
import { assetUrl, currentMode, postJSON } from "../../data/client";
import type { Case, Preview, Sources as SourcesT } from "../../data/types";
import { useT } from "../../app/settings";
import { Icon } from "../../icons";
import { DemoTag, ErrorState, LaneChip, Skeleton, Unavailable } from "../../components/ui";
import { useActions, useTicks } from "../../data/actions";

// 05 Verification sources + 05b preview drawer (560 px): exactly what each source sent back.
const when = (ts: string | null) => ts ? new Date(ts).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";

export function Sources({ c }: { c: Case }) {
  const t = useT();
  const v = useView<SourcesT>(`cases/${c.app_id}/sources`);
  const qc = useQueryClient();
  const [open, setOpen] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const reask = async () => {
    setBusy(true);
    try { if (currentMode() === "live") { await postJSON(`cases/${c.app_id}/sources/reask`, {}); qc.invalidateQueries(); } } finally { setBusy(false); }
  };
  return (
    <div className="tabpage">
      <div className="tabpage-head">
        <div><h3>{t("Asked")} {v.data?.count ?? ""} {t("outside sources about this file")}</h3>
          <p>{t("Press Preview to see exactly what each source sent back. Sources marked \"demo adapter\" return sample answers in this build.")}</p></div>
        <button className="btn" onClick={reask} disabled={busy}><Icon name="refresh" />{t("Ask all sources again")}</button>
      </div>
      {v.isLoading && <Skeleton rows={7} height={28} />}
      {v.isError && <ErrorState error={v.error} retry={() => v.refetch()} />}
      {v.data && (
        <table className="table">
          <thead><tr><th>{t("Source")}</th><th>{t("What Pramaan asked")}</th><th>{t("Answer")}</th><th>{t("When")}</th><th>{t("Result")}</th><th /></tr></thead>
          <tbody>{v.data.rows.map((r) => (
            <tr key={r.id}>
              <td style={{ whiteSpace: "nowrap" }}><span style={{ fontWeight: 500 }}>{r.source}</span> {r.demo && <DemoTag />}</td>
              <td>{r.asked}</td><td>{r.answer}</td><td className="muted" style={{ whiteSpace: "nowrap" }}>{when(r.when)}</td>
              <td><LaneChip lane={r.lane} text={r.result} /></td>
              <td style={{ textAlign: "end" }}>{r.preview ? <button className="btn small" onClick={() => setOpen(r.id)}><Icon name="visibility" />{t("Preview")}</button>
                : <span className="muted" style={{ fontSize: 12.5 }}>{t("Nothing to show")}</span>}</td>
            </tr>))}</tbody>
        </table>
      )}
      <p className="note">{t("Every question, answer and preview is written to the audit log with its hash.")}</p>
      {open !== null && <PreviewDrawer c={c} row={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

function PreviewDrawer({ c, row, onClose }: { c: Case; row: number; onClose: () => void }) {
  const t = useT();
  const appId = c.app_id;
  const p = useView<Preview>(`cases/${appId}/sources/${row}/preview`);
  const act = useActions();
  const ticked = useTicks(appId, c.findings);
  // WK27 G6: "Add to Letter of Deficiency" ticks the findings behind this source in the letter (the same tick as in the editor)
  const behind = c.findings.filter((f) => p.data?.doc_id && f.doc_id === p.data.doc_id && (f.lane === "return_for_rectification" || f.lane === "human_review"));
  const added = behind.length > 0 && behind.every((f) => ticked(f.finding_id, f.lane === "return_for_rectification"));
  return (
    <div className="modal-backdrop" style={{ placeItems: "stretch" }} onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={t("Preview")} onClick={(e) => e.stopPropagation()}>
        {!p.data ? <Skeleton rows={10} /> : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div><h2 style={{ fontSize: 22 }}>{t("Preview")}<span className="sep">·</span>{p.data.source} {p.data.demo && <DemoTag />}</h2>
                <p className="muted" style={{ margin: "4px 0 0", fontSize: 12.5 }}>{t("Asked for")}: {p.data.asked}<span className="sep">·</span>{when(p.data.when)}</p></div>
              <button className="iconbtn" style={{ border: 0 }} aria-label={t("Close")} onClick={onClose}><Icon name="close" /></button>
            </div>
            <div className="viewer" style={{ marginTop: 16, maxHeight: 360 }}>
              {p.data.image ? (
                <div className="paper"><img src={assetUrl(p.data.image)} alt={t("Returned document")} />
                  {p.data.box && <span className={`evbox ${p.data.lane === "clear" ? "clr" : "ret"}`} style={{ left: `${p.data.box.x0 * 100}%`, top: `${p.data.box.y0 * 100}%`,
                    width: `${(p.data.box.x1 - p.data.box.x0) * 100}%`, height: `${(p.data.box.y1 - p.data.box.y0) * 100}%` }} />}</div>
              ) : <div className="state"><p style={{ margin: 0 }}>{p.data.answer}</p></div>}
            </div>
            <table className="table kv" style={{ marginTop: 16 }}>
              <tbody>{p.data.kv.map((x) => <tr key={x.k}><td className="muted" style={{ width: 150 }}>{x.k}</td><td className={x.k.toLowerCase().includes("hash") || x.k.toLowerCase().includes("id") ? "mono" : ""}>{x.v}</td></tr>)}</tbody>
            </table>
            <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
              <Unavailable reason={t("Nothing from this source needs to go into the letter.")} active={!behind.length}>
                <button className="btn primary" disabled={added || !behind.length} onClick={() => behind.forEach((f) => act.tick(appId, f.finding_id, true))}>
                  {added ? t("In the letter draft") : t("Add to Letter of Deficiency")}</button>
              </Unavailable>
              {p.data.image && <a className="btn" href={assetUrl(p.data.image)} target="_blank" rel="noreferrer"><Icon name="open_in_new" />{t("Open full size")}</a>}
              {p.data.image && <a className="btn" href={assetUrl(p.data.image)} download><Icon name="download" />{t("Download")}</a>}
            </div>
            <p className="note">{p.data.note}</p>
          </>
        )}
      </aside>
    </div>
  );
}
