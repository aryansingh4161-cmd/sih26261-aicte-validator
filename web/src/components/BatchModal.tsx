import { useState } from "react";
import { useView } from "../data/hooks";
import { useActions } from "../data/actions";
import type { Batch, Case } from "../data/types";
import { useT } from "../app/settings";
import { Icon } from "../icons";
import { GearMark, Skeleton, StateBox, Unavailable } from "./ui";
import { ChecklistCounts, DocViewer, boxesFor } from "./case";

// 16 Batch-approve clear files: one random spot-check file must be opened and agreed first (queue.py, seeded).
export function BatchModal({ onClose }: { onClose: () => void }) {
  const t = useT();
  const b = useView<Batch>("batch");
  const act = useActions();
  const [opened, setOpened] = useState<string[]>([]);
  const [peek, setPeek] = useState(false);
  const [done, setDone] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const spot = b.data?.spot[0];
  const ready = !!spot && opened.includes(spot);
  const approve = async () => {
    setBusy(true);
    try { const r = await act.approveBatch(opened, b.data!.files.map((f) => f.app_id)); setDone(r.approved); } finally { setBusy(false); }
  };
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="batch-title" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 id="batch-title" style={{ fontSize: 24 }}>{done ? t("Approved and sealed.") : `${t("Approve")} ${b.data?.files.length ?? ""} ${t("clear files")}`}</h2>
          <button className="iconbtn" style={{ border: 0 }} aria-label={t("Close")} onClick={onClose}><Icon name="close" /></button>
        </div>
        {b.isLoading && <div style={{ marginTop: 16 }}><Skeleton rows={5} /></div>}
        {b.data && !b.data.files.length && <StateBox icon="inbox" title={t("No clear files right now.")} />}
        {done && (
          <div className="state" style={{ padding: "26px 0 8px" }}>
            <GearMark size={48} spin />
            <p style={{ margin: 0 }}>{done.length} {t("Letters of Approval drafted, sealed and put in the outbox.")}</p>
            <button className="btn" onClick={onClose}>{t("Done")}</button>
          </div>
        )}
        {b.data && b.data.files.length > 0 && !done && (
          <>
            <p className="muted" style={{ margin: "10px 0 14px" }}>{b.data.note}</p>
            {ready ? (
              <div className="okbox"><Icon name="check_circle" />
                <div><b>{t("Spot check done")}: {spot} {t("opened and agreed")}</b><div className="muted" style={{ fontSize: 12.5 }}>{b.data.files.find((f) => f.app_id === spot)?.institute}</div></div></div>
            ) : (
              <div className="spotbox">
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Icon name="visibility" style={{ color: "var(--rev)" }} />
                  <span><b>{t("Open")} <span className="mono">{spot}</span> {t("first")}</b> <span className="muted">({t("picked at random")})</span></span>
                  <button className="btn small" style={{ marginInlineStart: "auto" }} onClick={() => setPeek(!peek)}>{peek ? t("Hide") : t("Open")}</button>
                </div>
                {peek && spot && <SpotPeek appId={spot} onAgree={() => setOpened([...opened, spot])} />}
              </div>
            )}
            <ul className="batchlist">
              {b.data.files.map((f) => <li key={f.app_id}><Icon name="check_box" style={{ color: "var(--brand)" }} /><span className="mono">{f.app_id}</span>{f.institute}</li>)}
            </ul>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16 }}>
              <span className="muted" style={{ fontSize: 12.5, maxWidth: 250 }}>{t("Letters of Approval will be drafted, sealed and put in the outbox.")}</span>
              <button className="btn" style={{ marginInlineStart: "auto" }} onClick={onClose}>{t("Cancel")}</button>
              <Unavailable reason={t("Open the file picked for the spot check and agree first.")} active={!ready} align="end">
                <button className="btn primary" disabled={!ready || busy} onClick={approve}><Icon name="verified_user" />{t("Approve")} {b.data.files.length} {t("and seal")}</button>
              </Unavailable>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function SpotPeek({ appId, onAgree }: { appId: string; onAgree: () => void }) {
  const t = useT();
  const c = useView<Case>(`cases/${appId}`);
  if (!c.data) return <div style={{ marginTop: 10 }}><Skeleton rows={4} /></div>;
  const d = c.data.documents[0];
  return (
    <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "180px 1fr", gap: 14 }}>
      <DocViewer src={d?.page_urls[0]} boxes={d ? boxesFor(c.data, d.doc_id) : []} height={200} />
      <div style={{ fontSize: 13 }}>
        <b>{c.data.institute}</b>
        <p style={{ margin: "6px 0" }}><ChecklistCounts c={c.data.checklist} /></p>
        <p className="muted" style={{ margin: "0 0 10px" }}>{c.data.documents.length} {t("documents")}, {c.data.findings.length} {t("findings")}</p>
        <button className="btn small" onClick={onAgree}><Icon name="check_circle" />{t("I opened it and agree")}</button>
      </div>
    </div>
  );
}
