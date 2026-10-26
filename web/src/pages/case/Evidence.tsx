import { useState } from "react";
import { useView } from "../../data/hooks";
import { currentMode } from "../../data/client";
import { useActions, useDemoActions } from "../../data/actions";
import type { Case, Note } from "../../data/types";
import { useT } from "../../app/settings";
import { Icon } from "../../icons";
import { LaneIcon, Skeleton } from "../../components/ui";
import { DocViewer, FindingCard, boxesFor } from "../../components/case";

// 03 Case view: Evidence. Document list | viewer (evidence boxes, tamper heatmap toggle) | findings, tamper check, internal notes.
export function Evidence({ c }: { c: Case }) {
  const t = useT();
  const first = c.findings.find((f) => f.doc_id && f.lane !== "info")?.doc_id || c.documents[0]?.doc_id;
  const [docId, setDocId] = useState(first);
  const [page, setPage] = useState(1);
  const [boxes, setBoxes] = useState(true);
  const [heat, setHeat] = useState(false);
  const doc = c.documents.find((d) => d.doc_id === docId) || c.documents[0];
  const onDoc = c.findings.filter((f) => f.doc_id === doc?.doc_id);
  const heatUrl = doc?.heatmap_urls[String(page)];
  return (
    <div className="evidence">
      <aside className="doclist" aria-label={t("Documents")}>
        <div className="eyebrow" style={{ color: "var(--muted)", margin: "0 0 8px 10px" }}>{t("Documents")}<span style={{ marginInlineStart: 10 }}>{c.documents.length}</span></div>
        {c.documents.map((d) => (
          <button key={d.doc_id} className={"docitem" + (d.doc_id === doc?.doc_id ? " on" : "")} aria-current={d.doc_id === doc?.doc_id}
            onClick={() => { setDocId(d.doc_id); setPage(1); }}>
            <LaneIcon lane={d.status} size={16} /><span className="name">{d.label}</span><span className="muted pages">{d.pages} p</span>
          </button>
        ))}
        {c.findings.some((f) => !f.doc_id) && (
          <p className="note" style={{ margin: "12px 10px" }}>{t("Some findings are about the whole file (missing documents, cross-checks, photos): see the right column.")}</p>
        )}
      </aside>
      <section className="viewcol">
        <div className="viewbar">
          <b>{doc?.label}</b><span className="muted">{t("page")} {page} {t("of")} {doc?.pages}</span>
          <span style={{ marginInlineStart: "auto", display: "flex", gap: 6 }}>
            {doc && doc.pages > 1 && <>
              <button className="btn small" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label={t("Previous page")}>{"<"}</button>
              <button className="btn small" disabled={page >= doc.pages} onClick={() => setPage(page + 1)} aria-label={t("Next page")}>{">"}</button></>}
            <button className={"btn small" + (boxes ? " on" : "")} aria-pressed={boxes} onClick={() => setBoxes(!boxes)}>{t("Evidence boxes")}</button>
            <button className={"btn small" + (heat ? " on" : "")} aria-pressed={heat} disabled={!heatUrl} onClick={() => setHeat(!heat)}
              title={heatUrl ? "" : t("No heatmap: the tamper model runs on scanned pages")}>{t("Tamper heatmap")}</button>
          </span>
        </div>
        <div className="viewwrap">
          <DocViewer src={doc?.page_urls[page - 1]} boxes={boxes && doc ? boxesFor(c, doc.doc_id, page) : []} heat={heatUrl} showHeat={heat} height={640} />
        </div>
        <p className="note" style={{ textAlign: "center" }}>{t("Red: to return. Orange: to check. The boxes show where Pramaan looked.")}</p>
      </section>
      <aside className="sidecol">
        <h3 className="sec">{t("On this document")}</h3>
        {onDoc.length ? onDoc.map((f) => <FindingCard key={f.finding_id} appId={c.app_id} f={f} />)
          : <div className="finding"><div className="finding-top"><LaneIcon lane="clear" /><span className="finding-title" style={{ marginTop: 0 }}>{t("No findings on this document")}</span></div></div>}
        {c.findings.filter((f) => !f.doc_id).map((f) => <FindingCard key={f.finding_id} appId={c.app_id} f={f} />)}
        <div className="tamperbox"><Icon name={c.tamper.found ? "warning" : "verified_user"} style={{ color: c.tamper.found ? "var(--rev)" : "var(--clr)" }} />
          <div><b>{c.tamper.text}</b><div className="muted" style={{ fontSize: 12.5 }}>{t("Model 1 heatmap on scanned pages; text PDFs: file-structure checks")}</div></div></div>
        <h3 className="sec" style={{ marginTop: 20 }}>{t("Internal notes")}</h3>
        <NotesList appId={c.app_id} />
      </aside>
    </div>
  );
}

export function NotesList({ appId }: { appId: string }) {
  const t = useT();
  const n = useView<Note[]>(`cases/${appId}/notes`);
  const demo = useDemoActions();
  const act = useActions();
  const [text, setText] = useState("");
  const list = [...(n.data || []), ...(currentMode() === "demo" ? demo.notes[appId] || [] : [])];
  const add = async () => { if (text.trim()) { await act.note(appId, text.trim()); setText(""); } };
  return (
    <div>
      {n.isLoading && <Skeleton rows={2} />}
      {list.map((x, i) => (
        <div key={i} className="note-card"><div>{x.text}</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{x.author}<span className="sep">·</span>{new Date(x.ts).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</div></div>
      ))}
      <form className="note-add" onSubmit={(e) => { e.preventDefault(); add(); }}>
        <Icon name="chat" />
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t("Add a note. Never sent to the institute.")} aria-label={t("Add a note")} />
      </form>
    </div>
  );
}
