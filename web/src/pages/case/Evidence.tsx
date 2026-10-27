import { useEffect, useLayoutEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import { useView } from "../../data/hooks";
import { assetUrl, currentMode } from "../../data/client";
import { useActions, useDemoActions } from "../../data/actions";
import type { Box, Case, Doc, Finding, Note } from "../../data/types";
import { useT } from "../../app/settings";
import { Icon } from "../../icons";
import { LaneIcon, Skeleton, Unavailable, laneClass } from "../../components/ui";
import { FindingCard } from "../../components/case";

// 03 Case view: Evidence (WK27 D2). Two columns: the document viewer (left) and one issues panel (right). Internal notes live on
// the Notes tab only; the tamper result is one line in the panel. Issues are numbered once for the whole file, and the same number
// marks the box on the page. Selecting an issue opens its document and page and shows the region in the magnifier callout.
type Issue = { f: Finding; n: number; doc: string | null; page: number; box: Box | null };

const ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3];
const CALLOUT = 196;          // magnifier diameter (px)
const MAG = 2.5;              // magnifier enlargement

function issuesOf(c: Case): Issue[] {
  const order = new Map(c.documents.map((d, i) => [d.doc_id, i]));
  const list = c.findings.filter((f) => f.lane !== "clear").map((f) => {
    const ev = f.evidence.find((e) => e.bbox) || f.evidence.find((e) => e.doc_id) || null;
    return { f, n: 0, doc: ev?.doc_id || f.doc_id, page: ev?.page || 1, box: ev?.bbox || null };
  });
  const rank = (i: Issue) => (i.f.group === "doc" ? 0 : i.f.group === "photo" ? 1 : 2) * 1000 + (order.get(i.doc || "") ?? 999);
  return list.sort((a, b) => rank(a) - rank(b)).map((x, k) => ({ ...x, n: k + 1 }));
}

export function Evidence({ c }: { c: Case }) {
  const t = useT();
  const issues = useMemo(() => issuesOf(c), [c]);
  const first = issues.find((i) => i.doc)?.doc || c.documents[0]?.doc_id;
  const [docId, setDocId] = useState(first);
  const [page, setPage] = useState(issues.find((i) => i.doc === first)?.page || 1);
  const [sel, setSel] = useState<string | null>(null);
  const [heat, setHeat] = useState(false);
  const doc = c.documents.find((d) => d.doc_id === docId) || c.documents[0];
  const idx = c.documents.indexOf(doc);
  const go = (d: Doc, p = 1) => { setDocId(d.doc_id); setPage(p); setSel(null); setHeat(false); };
  const pick = (i: Issue) => {
    const d = c.documents.find((x) => x.doc_id === i.doc);
    if (d) { setDocId(d.doc_id); setPage(i.page); setHeat(false); }
    setSel(i.f.finding_id);
  };
  const onPage = issues.filter((i) => i.doc === doc?.doc_id && i.page === page);
  const selected = issues.find((i) => i.f.finding_id === sel && i.doc === doc?.doc_id && i.page === page && i.box) || null;
  const heatUrl = doc?.heatmap_urls[String(page)];
  const heatWhy = doc?.kind === "photo" ? t("Only for scanned pages. Photos are checked by their metadata instead.")
    : !doc?.scanned ? t("Only for scanned pages. This is a text PDF: its file structure was checked instead.")
    : !heatUrl ? t("No heatmap was saved for this page.") : "";
  return (
    <div className="ev2">
      <section className="ev-view" aria-label={t("Document viewer")}>
        <div className="ev-docbar">
          <DocSwitcher c={c} doc={doc} onPick={(d) => go(d)} />
          <span className="muted nowrap">{idx + 1} {t("of")} {c.documents.length}</span>
          <span className="btnpair">
            <button className="btn icon" disabled={idx <= 0} onClick={() => go(c.documents[idx - 1])} aria-label={t("Previous document")} title={t("Previous document")}><Icon name="chevron_left" /></button>
            <button className="btn icon" disabled={idx >= c.documents.length - 1} onClick={() => go(c.documents[idx + 1])} aria-label={t("Next document")} title={t("Next document")}><Icon name="chevron_right" /></button>
          </span>
        </div>
        <Stage key={doc?.doc_id + ":" + page} doc={doc} page={page} issues={onPage} selected={selected} heat={heat && !!heatUrl}
          heatUrl={heatUrl} onSelect={(i) => setSel(i ? i.f.finding_id : null)}
          toolbar={(zoomUi) => (
            <div className="ev-tools">
              <div className="seg" role="group" aria-label={t("What to show on the page")}>
                <button className={!heat ? "on" : ""} aria-pressed={!heat} onClick={() => setHeat(false)}>{t("Evidence boxes")}</button>
                <Unavailable reason={heatWhy} active={!!heatWhy}>
                  <button className={heat ? "on" : ""} aria-pressed={heat} disabled={!!heatWhy} onClick={() => setHeat(true)}>{t("Tamper heatmap")}</button>
                </Unavailable>
              </div>
              {zoomUi}
              {doc && doc.pages > 1 && (
                <span className="btnpair">
                  <button className="btn icon" disabled={page <= 1} onClick={() => { setPage(page - 1); setSel(null); }} aria-label={t("Previous page")}><Icon name="chevron_left" /></button>
                  <span className="muted nowrap">{t("page")} {page} {t("of")} {doc.pages}</span>
                  <button className="btn icon" disabled={page >= doc.pages} onClick={() => { setPage(page + 1); setSel(null); }} aria-label={t("Next page")}><Icon name="chevron_right" /></button>
                </span>
              )}
            </div>
          )} />
      </section>
      <IssuesPanel c={c} issues={issues} doc={doc} sel={sel} onPick={pick} onDoc={(id) => { const d = c.documents.find((x) => x.doc_id === id); if (d) go(d); }} />
    </div>
  );
}

function DocSwitcher({ c, doc, onPick }: { c: Case; doc: Doc; onPick: (d: Doc) => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", h); document.addEventListener("keydown", k);
    return () => { document.removeEventListener("mousedown", h); document.removeEventListener("keydown", k); };
  }, [open]);
  return (
    <div ref={ref} className="dd-wrap docswitch">
      <button className="select dd" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)} title={doc.label}>
        <LaneIcon lane={doc.status} size={16} /><span className="dd-val">{t("Document")}: <b>{doc.label}</b></span><Icon name="keyboard_arrow_down" />
      </button>
      {open && (
        <div className="pop menu" role="listbox" aria-label={t("Documents")}>
          {c.documents.map((d) => (
            <button key={d.doc_id} role="option" aria-selected={d.doc_id === doc.doc_id} className={"menu-item" + (d.doc_id === doc.doc_id ? " on" : "")}
              onClick={() => { onPick(d); setOpen(false); }} title={d.label}>
              <LaneIcon lane={d.status} size={16} />{d.kind === "photo" && <Icon name="photo" size={16} />}
              <span className="mi-text">{d.label}</span><span className="muted" style={{ marginInlineStart: "auto", fontSize: 12 }}>{d.pages} p</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** The page: zoom (buttons, Ctrl / Cmd + wheel), drag to pan when zoomed, numbered evidence boxes, the magnifier callout. */
function Stage({ doc, page, issues, selected, heat, heatUrl, onSelect, toolbar }: { doc: Doc; page: number; issues: Issue[];
  selected: Issue | null; heat: boolean; heatUrl?: string; onSelect: (i: Issue | null) => void; toolbar: (zoomUi: JSX.Element) => JSX.Element }) {
  const t = useT();
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600);
  const [aspect, setAspect] = useState(1.414);
  const [zoom, setZoom] = useState(1);
  const [broken, setBroken] = useState(false);
  const drag = useRef<{ x: number; y: number; l: number; t: number } | null>(null);
  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el); setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  useEffect(() => {                                              // Ctrl / Cmd + wheel zooms (not the browser page)
    const el = wrap.current;
    if (!el) return;
    const w = (e: WheelEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      setZoom((z) => Math.min(3, Math.max(0.5, +(z * (e.deltaY < 0 ? 1.1 : 1 / 1.1)).toFixed(2))));
    };
    el.addEventListener("wheel", w, { passive: false });
    return () => el.removeEventListener("wheel", w);
  }, []);
  const callout = !!selected?.box && !heat;
  const fit = Math.max(260, Math.min(720, width - 48 - (callout ? CALLOUT + 72 : 0)));
  const W = Math.round(fit * zoom), H = Math.round(W * aspect);
  const src = doc?.page_urls[page - 1];
  const clean = !issues.length && !broken && !!src;
  useEffect(() => {                                              // bring the selected box into view
    if (!selected?.box || !wrap.current) return;
    const el = wrap.current, b = selected.box;
    el.scrollTo({ left: Math.max(0, b.x0 * W - 60), top: Math.max(0, b.y0 * H - 120), behavior: "smooth" });
  }, [selected, W, H]);
  const down = (e: RPointerEvent) => {
    if (zoom <= 1 || !wrap.current || (e.target as HTMLElement).closest("button")) return;
    drag.current = { x: e.clientX, y: e.clientY, l: wrap.current.scrollLeft, t: wrap.current.scrollTop };
    wrap.current.setPointerCapture(e.pointerId);
  };
  const move = (e: RPointerEvent) => {
    if (!drag.current || !wrap.current) return;
    wrap.current.scrollLeft = drag.current.l - (e.clientX - drag.current.x);
    wrap.current.scrollTop = drag.current.t - (e.clientY - drag.current.y);
  };
  const step = (dir: number) => setZoom((z) => (dir > 0 ? ZOOMS.find((x) => x > z + 0.01) ?? 3 : [...ZOOMS].reverse().find((x) => x < z - 0.01) ?? 0.5));
  const zoomUi = (
    <span className="btnpair zoom" role="group" aria-label={t("Zoom")}>
      <button className="btn icon" onClick={() => step(-1)} aria-label={t("Zoom out")} title={t("Zoom out")}><Icon name="remove" /></button>
      <span className="mono zoomval" aria-live="polite">{Math.round(zoom * 100)}%</span>
      <button className="btn icon" onClick={() => step(1)} aria-label={t("Zoom in")} title={t("Zoom in")}><Icon name="add" /></button>
      <button className="btn" onClick={() => setZoom(1)} title={t("Fit the page to the viewer")}>{t("Fit")}</button>
    </span>
  );
  // magnifier geometry (stage coordinates)
  const PAD = 24;
  let mag = null as null | { cx: number; cy: number; bx: number; by0: number; by1: number; bgx: number; bgy: number };
  if (callout && selected?.box) {
    const b = selected.box;
    const bx = PAD + b.x1 * W, by0 = PAD + b.y0 * H, by1 = PAD + b.y1 * H;
    const cx = PAD + W + 48 + CALLOUT / 2;
    const cy = Math.min(Math.max(PAD + CALLOUT / 2, (by0 + by1) / 2), PAD + Math.max(H, CALLOUT + 40) - CALLOUT / 2 - 30);
    const mx = ((b.x0 + b.x1) / 2) * W * MAG, my = ((b.y0 + b.y1) / 2) * H * MAG;
    mag = { cx, cy, bx, by0, by1, bgx: CALLOUT / 2 - mx, bgy: CALLOUT / 2 - my };
  }
  return (
    <>
      {toolbar(zoomUi)}
      <div ref={wrap} className={"stage" + (zoom > 1 ? " pan" : "")} onPointerDown={down} onPointerMove={move}
        onPointerUp={() => { drag.current = null; }} tabIndex={0} role="region" aria-label={t("Document page, scroll to read")}>
        <div className="stage-inner" style={{ width: PAD * 2 + W + (callout ? CALLOUT + 72 : 0), minHeight: PAD * 2 + Math.max(H, callout ? CALLOUT + 70 : 0) }}>
          {clean && <span className="chip clr cleanchip"><Icon name="check_circle" />{t("No problems found on this page")}</span>}
          <div className={"paper2" + (clean ? " clean" : "")} style={{ width: W, height: broken ? 320 : H, left: PAD, top: PAD }}>
            {src && !broken ? <img src={assetUrl(src)} alt={`${doc.label}, ${t("page")} ${page}`} draggable={false}
              onLoad={(e) => { const i = e.currentTarget; if (i.naturalWidth) setAspect(i.naturalHeight / i.naturalWidth); }} onError={() => setBroken(true)} />
              : <div className="state"><Icon name="do_not_disturb_on" size={32} /><h3>{t("This page could not be shown.")}</h3>
                  <p style={{ margin: 0 }}>{t("It is marked \"Not automated\" so it is never passed silently.")}</p></div>}
            {heat && heatUrl && <img className="heat" src={assetUrl(heatUrl)} alt={t("Tamper heatmap")} />}
            {!heat && issues.filter((i) => i.box).map((i) => {
              const b = i.box as Box;
              return (
                <button key={i.f.finding_id} className={`evbox2 ${laneClass(i.f.lane)}` + (selected?.f.finding_id === i.f.finding_id ? " sel" : "")}
                  style={{ left: `${b.x0 * 100}%`, top: `${b.y0 * 100}%`, width: `${(b.x1 - b.x0) * 100}%`, height: `${(b.y1 - b.y0) * 100}%` }}
                  onClick={() => onSelect(selected?.f.finding_id === i.f.finding_id ? null : i)} aria-label={`${t("Issue")} ${i.n}: ${i.f.title}`}>
                  <span className="evnum">{i.n}</span>
                </button>
              );
            })}
          </div>
          {mag && selected && src && (
            <>
              <svg className="maglines" width="100%" height="100%" aria-hidden="true">
                <line x1={mag.bx} y1={mag.by0} x2={mag.cx} y2={mag.cy - CALLOUT / 2} />
                <line x1={mag.bx} y1={mag.by1} x2={mag.cx} y2={mag.cy + CALLOUT / 2} />
              </svg>
              <figure className={`magnifier ${laneClass(selected.f.lane)}`} style={{ left: mag.cx - CALLOUT / 2, top: mag.cy - CALLOUT / 2 }}>
                <div className="lens" style={{ width: CALLOUT, height: CALLOUT, backgroundImage: `url("${assetUrl(src)}")`,
                  backgroundSize: `${W * MAG}px ${H * MAG}px`, backgroundPosition: `${mag.bgx}px ${mag.bgy}px` }}
                  role="img" aria-label={`${t("Enlarged")}: ${selected.f.title}`} />
                <figcaption><span className={`evnum inline ${laneClass(selected.f.lane)}`}>{selected.n}</span>{selected.f.title}</figcaption>
              </figure>
            </>
          )}
        </div>
      </div>
      <p className="note" style={{ marginTop: 8 }}>{heat ? t("Heatmap: darker areas are where the tamper model sees possible edits. It is advisory.")
        : t("Red: to return. Orange: to check. Click a box or an issue to enlarge it.")}</p>
    </>
  );
}

function IssuesPanel({ c, issues, doc, sel, onPick, onDoc }: { c: Case; issues: Issue[]; doc: Doc; sel: string | null; onPick: (i: Issue) => void;
  onDoc: (docId: string) => void }) {
  const t = useT();
  const here = issues.filter((i) => i.f.group === "doc" && i.doc === doc.doc_id);
  const elsewhere = issues.filter((i) => i.f.group === "doc" && i.doc !== doc.doc_id);
  const photos = issues.filter((i) => i.f.group === "photo");
  const file = issues.filter((i) => i.f.group === "file");
  const others = [...new Set(elsewhere.map((i) => i.doc))].map((d) => ({ d, n: elsewhere.filter((i) => i.doc === d).length,
    label: c.documents.find((x) => x.doc_id === d)?.label || d }));
  return (
    <aside className="ev-issues" aria-label={t("Issues")}>
      <h3 className="sec">{t("Issues")} ({issues.length})</h3>
      {!issues.length && <p className="muted" style={{ marginTop: 0 }}>{t("Pramaan found nothing to look at in this file. The officer still decides.")}</p>}
      <Section title={t("This document")} count={here.length}>
        {here.map((i) => <IssueCard key={i.f.finding_id} c={c} i={i} on={sel === i.f.finding_id} onPick={onPick} />)}
        {!here.length && (doc.kind === "photo" && photos.some((i) => i.doc === doc.doc_id)
          ? <p className="muted small">{t("This photo's issues are under Photos and metadata.")} ({photos.filter((i) => i.doc === doc.doc_id).length})</p>
          : <p className="muted small">{t("No problems found on this document.")}</p>)}
        {others.length > 0 && <p className="muted small">{t("On other documents")}: {others.map((o, k) => (
          <span key={o.d}>{k > 0 && ", "}<button className="linkbtn" onClick={() => o.d && onDoc(o.d)}>{o.label}</button> ({o.n})</span>))}</p>}
      </Section>
      {photos.length > 0 && <Section title={t("Photos and metadata")} count={photos.length}>
        {photos.map((i) => <IssueCard key={i.f.finding_id} c={c} i={i} on={sel === i.f.finding_id} onPick={onPick} />)}
      </Section>}
      <Section title={t("Whole file (cross-checks, missing documents)")} count={file.length}>
        {file.map((i) => <IssueCard key={i.f.finding_id} c={c} i={i} on={sel === i.f.finding_id} onPick={onPick} />)}
        {!file.length && <p className="muted small">{t("Nothing found across the file.")}</p>}
      </Section>
      <p className="tamperline"><Icon name={c.tamper.found ? "warning" : "verified_user"} size={16} style={{ color: c.tamper.found ? "var(--rev)" : "var(--clr)" }} />{c.tamper.text}</p>
    </aside>
  );
}

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <section className="isec">
      <button className="isec-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon name="keyboard_arrow_down" className={open ? "" : "turned"} /><span className="isec-title" title={title}>{title}</span><span className="isec-n">{count}</span>
      </button>
      {open && <div className="isec-body">{children}</div>}
    </section>
  );
}

function IssueCard({ c, i, on, onPick }: { c: Case; i: Issue; on: boolean; onPick: (i: Issue) => void }) {
  return (
    <div className={"issue" + (on ? " on" : "")} onClick={(e) => { if (!(e.target as HTMLElement).closest(".finding-top button")) onPick(i); }}>
      <span className={`evnum inline ${laneClass(i.f.lane)}`} aria-hidden="true">{i.n}</span>
      <FindingCard appId={c.app_id} f={i.f} oneLine />
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
