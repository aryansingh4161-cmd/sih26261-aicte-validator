import { useState } from "react";
import { useView } from "../data/hooks";
import { currentMode, postJSON } from "../data/client";
import { useDemoActions } from "../data/actions";
import type { LetterRow, OutboxRow } from "../data/types";
import { useSettings } from "../app/settings";
import { Icon } from "../icons";
import { ErrorState, Skeleton } from "../components/ui";

// 09 Letters and outbox: Drafts / Sealed / Sent, seal hash, PDF (print the sealed HTML), Verify (seal.verify_sealed on the server).
const STATUS: Record<string, [string, string]> = { draft: ["rev", "visibility"], sealed: ["na", "do_not_disturb_on"], sent: ["clr", "check_circle"] };

export function Letters() {
  const { t, mode } = useSettings();
  const v = useView<{ letters: LetterRow[]; counts: Record<string, number>; headline: string }>("letters");
  const box = useView<OutboxRow[]>("outbox");
  const demo = useDemoActions();
  const [tab, setTab] = useState("all");
  const [verifyOpen, setVerifyOpen] = useState(false);
  const [result, setResult] = useState<Record<string, string>>({});
  const local: LetterRow[] = currentMode() === "demo" ? Object.entries(demo.sealed).map(([a, s]) => ({ kind: "Letter of Deficiency", kind_label: t("Letter of Deficiency"),
    app_id: a, institute: t("(sealed in this browser)"), status: "sealed", status_label: t("Sealed, not sent"), hash: "#" + s.hash.slice(0, 6), date: s.ts.slice(0, 10), file: null })) : [];
  const all = [...local, ...(v.data?.letters || []).filter((l) => !(l.status === "draft" && demo.sealed[l.app_id]))];
  const rows = tab === "all" ? all : all.filter((l) => l.status === tab);
  const n = (s: string) => all.filter((l) => l.status === s).length;
  const fileUrl = (f: string) => (mode === "live" ? `/api/letters/file/${f}` : `${import.meta.env.BASE_URL}snapshot/letters/${f}`);
  const verify = async (l: LetterRow) => {
    if (mode === "live" && l.file) { const r = await postJSON<{ result: string }>("letters/verify", { file: l.file }); setResult({ ...result, [l.app_id + l.date]: r.result }); }
    else setResult({ ...result, [l.app_id + l.date]: l.verify || t("Not sealed yet") });
  };
  return (
    <div className="page">
      <div className="page-head">
        <div><span className="eyebrow">{t("Regulation Bureau")}<span className="sep">·</span>{t("All regions")}</span>
          <h1>{t("Letters and outbox.")}<span className="line2">{v.data ? v.data.headline : " "}</span></h1></div>
        <button className="btn" onClick={() => setVerifyOpen(true)}><Icon name="verified_user" />{t("Verify a sealed letter")}</button>
      </div>
      <div className="subtabs" role="tablist">
        {[["draft", "Drafts"], ["sealed", "Sealed"], ["sent", "Sent"], ["all", "All"], ["outbox", "Outbox"]].map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>
            {t(l)}{k !== "all" && k !== "outbox" && <span className="muted"> {n(k)}</span>}</button>))}
      </div>
      {v.isLoading && <Skeleton rows={8} height={26} />}
      {v.isError && <ErrorState error={v.error} retry={() => v.refetch()} />}
      {tab === "outbox" ? (
        <table className="table">
          <thead><tr><th>{t("Created")}</th><th>{t("Channel")}</th><th>{t("To")}</th><th>{t("Subject")}</th></tr></thead>
          <tbody>{(box.data || []).map((o) => <tr key={o.id}><td className="muted">{o.created_at.replace("T", " ").slice(0, 16)}</td>
            <td>{o.channel.replace(" (MOCK)", "")} <span className="tag-demo">{t("demo adapter")}</span></td><td>{o.to}</td><td>{o.subject}</td></tr>)}</tbody>
        </table>
      ) : v.data && (
        <table className="table">
          <thead><tr><th>{t("Letter")}</th><th>{t("Institute")}</th><th>{t("File")}</th><th>{t("Status")}</th><th>{t("Seal hash")}</th><th>{t("Date")}</th><th /></tr></thead>
          <tbody>{rows.map((l) => {
            const [cls, ic] = STATUS[l.status];
            const res = result[l.app_id + l.date];
            return (
              <tr key={l.kind + l.app_id + l.date}>
                <td>{l.kind_label}</td><td>{l.institute}</td><td><span className="chip plain mono">{l.app_id}</span></td>
                <td><span className={`chip ${cls}`}><Icon name={ic} />{l.status_label}</span></td>
                <td className="mono">{l.hash || <span className="muted">{t("not sealed")}</span>}</td>
                <td>{new Date(l.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</td>
                <td style={{ whiteSpace: "nowrap", textAlign: "end" }}>
                  {l.file ? <a className="btn small" href={fileUrl(l.file)} target="_blank" rel="noreferrer">PDF</a> : <button className="btn small" disabled>PDF</button>}{" "}
                  <button className="btn small" onClick={() => verify(l)}>{t("Verify")}</button>
                  {res && <div className={res.startsWith("VALID") ? "t-clr" : "t-rev"} style={{ fontSize: 12, marginTop: 4, whiteSpace: "normal", maxWidth: 220 }}>{res}</div>}
                </td>
              </tr>);
          })}</tbody>
        </table>
      )}
      <p className="note">{t("Anyone can check a sealed letter: scan its QR code or run the verify tool. A letter that was changed after sealing will not match its hash.")}</p>
      {verifyOpen && <VerifyModal onClose={() => setVerifyOpen(false)} />}
    </div>
  );
}

function VerifyModal({ onClose }: { onClose: () => void }) {
  const { t, mode } = useSettings();
  const [res, setRes] = useState<string | null>(null);
  const check = async (f: File) => {
    const html = await f.text();
    if (mode !== "live") { setRes(t("Verification runs on the server against the audit chain. In this demo, use Verify on a row of the table.")); return; }
    setRes((await postJSON<{ result: string }>("letters/verify", { html })).result);
  };
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={t("Verify a sealed letter")} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between" }}><h2 style={{ fontSize: 22 }}>{t("Verify a sealed letter")}</h2>
          <button className="iconbtn" style={{ border: 0 }} aria-label={t("Close")} onClick={onClose}><Icon name="close" /></button></div>
        <p className="muted">{t("Choose the sealed letter file (HTML). Pramaan recomputes its hash and looks for the matching block in the audit chain.")}</p>
        <input type="file" accept=".html,text/html" onChange={(e) => e.target.files?.[0] && check(e.target.files[0])} aria-label={t("Sealed letter file")} />
        {res && <p className={res.startsWith("VALID") ? "t-clr" : "t-rev"} style={{ marginTop: 14, fontWeight: 500 }}>{res}</p>}
      </div>
    </div>
  );
}
