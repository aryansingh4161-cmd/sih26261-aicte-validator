import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useView } from "../data/hooks";
import { currentMode } from "../data/client";
import { useActions, useDemoActions } from "../data/actions";
import type { Case, Officer, Queue, QueueItem } from "../data/types";
import { useSettings } from "../app/settings";
import { Icon } from "../icons";
import { EmptyQueue, ErrorState, LaneChip, Skeleton } from "../components/ui";
import { AppealText, ChainTimeline, ChecklistCounts, DocViewer, FindingCard, TrustBar, boxesFor } from "../components/case";
import { BatchModal } from "../components/BatchModal";
import { LanguageNote } from "../components/Shell";

// 02 Home: my queue (Option 3 "Desk"): queue list (420 px) + the selected file's preview.
export function Dropdown({ label, value, options, onChange }: { label: string; value: string; options: [string, string][]; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  const cur = options.find(([v]) => v === value)?.[1] ?? options[0][1];
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button className="select dd" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
        <span>{label}: {cur}</span><Icon name="keyboard_arrow_down" />
      </button>
      {open && (
        <div className="pop" role="listbox" aria-label={label} style={{ top: 40, insetInlineStart: 0, minWidth: 200, padding: "6px 0" }}>
          {options.map(([v, l]) => (
            <button key={v} role="option" aria-selected={v === value} className={"menu-item" + (v === value ? " on" : "")}
              onClick={() => { onChange(v); setOpen(false); }}>{l}</button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Home() {
  const { t } = useSettings();
  const nav = useNavigate();
  const [lane, setLane] = useState(""); const [due, setDue] = useState(""); const [sort, setSort] = useState("priority");
  const q = useView<Queue>("queue", { lane, due, sort });
  const demo = useDemoActions();
  const items = useMemo(() => {
    let list = q.data?.items || [];
    if (currentMode() === "demo") {                       // the demo snapshot has one list per role: filter and sort it here
      list = list.filter((i) => !demo.approved.includes(i.app_id) && (!lane || i.lane === lane)
        && (!due || (due === "today" ? i.due_word === "Today" || i.due_word === "Overdue" : true)));
      if (sort === "due") list = [...list].sort((a, b) => a.due_by.localeCompare(b.due_by));
      if (sort === "trust") list = [...list].sort((a, b) => a.trust - b.trust);
    }
    return list;
  }, [q.data, demo.approved, lane, due, sort]);
  const [sel, setSel] = useState<string | null>(null);
  const [batch, setBatch] = useState(false);
  const current = items.find((i) => i.app_id === sel) || items[0];
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (/INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName) || !items.length) return;
      const i = Math.max(0, items.findIndex((x) => x.app_id === current?.app_id));
      if (e.key === "j") setSel(items[Math.min(items.length - 1, i + 1)].app_id);
      if (e.key === "k") setSel(items[Math.max(0, i - 1)].app_id);
      if (e.key === "Enter" && current && document.activeElement?.closest(".qlist")) nav(`/case/${current.app_id}`);
    };
    document.addEventListener("keydown", k);
    return () => document.removeEventListener("keydown", k);
  }, [items, current, nav]);
  const clear = items.filter((i) => i.lane === "clear").length;
  return (
    <div className="home">
      <section className="qpane" aria-label={t("Your queue")}>
        <div className="qhead">
          <span className="eyebrow">{q.data ? q.data.role.name : t("Regulation Bureau")}<span className="sep">·</span>{t("All regions")}</span>
          <h1>{t("Your queue.")}<span className="line2">{q.data ? `${items.length} ${t("waiting.")}` : " "}</span></h1>
          {q.data && <p className="muted" style={{ margin: "8px 0 0", fontSize: 13 }}>{q.data.summary}</p>}
          <div className="filters">
            <Dropdown label={t("Lane")} value={lane} onChange={setLane} options={[["", t("All")], ["return_for_rectification", t("Return for rectification")],
              ["human_review", t("Human review")], ["clear", t("Clear")]]} />
            <Dropdown label={t("Due")} value={due} onChange={setDue} options={[["", t("Any")], ["today", t("Today")], ["week", t("This week")]]} />
            <span style={{ marginInlineStart: "auto" }}>
              <Dropdown label={t("Sort")} value={sort} onChange={setSort} options={[["priority", t("Priority")], ["due", t("Due date")], ["trust", t("Trust")]]} />
            </span>
          </div>
          {clear > 0 && <button className="btn small" style={{ marginTop: 10 }} onClick={() => setBatch(true)}>
            <Icon name="task_alt" />{t("Approve clear files")} ({clear})</button>}
          <LanguageNote />
        </div>
        <div className="qlist" ref={listRef} role="listbox" aria-label={t("Files")} tabIndex={0}>
          {q.isLoading && <div style={{ padding: 24 }}><Skeleton rows={8} height={46} /></div>}
          {q.isError && <ErrorState error={q.error} retry={() => q.refetch()} />}
          {q.data && !items.length && <EmptyQueue />}
          {items.map((i) => <QueueRow key={i.app_id} i={i} on={i.app_id === current?.app_id} onClick={() => setSel(i.app_id)} onOpen={() => nav(`/case/${i.app_id}`)} />)}
        </div>
      </section>
      <section className="preview" aria-label={t("Selected file")}>{current ? <Preview item={current} index={items.indexOf(current)} /> : null}</section>
      {batch && <BatchModal onClose={() => setBatch(false)} />}
    </div>
  );
}

function QueueRow({ i, on, onClick, onOpen }: { i: QueueItem; on: boolean; onClick: () => void; onOpen: () => void }) {
  const { t } = useSettings();
  const urgent = i.due_word === "Today" || i.due_word === "Overdue" || i.due_word === t("Today") || i.due_word === t("Overdue");
  return (
    <div role="option" aria-selected={on} className={"qrow" + (on ? " on" : "")} onClick={onClick} onDoubleClick={onOpen}>
      <div className="qrow-top"><span className="inst">{i.institute}</span><span className={urgent ? "t-ret due" : "muted due"}>{i.due_word}</span></div>
      <div className="meta"><span className="mono">{i.app_id}</span><span className="sep">·</span>{i.category}<span className="sep">·</span>{t("Trust")} {i.trust}</div>
      <div className="qrow-line"><LaneChip lane={i.lane} short /><span className="headline">{i.headline}</span></div>
    </div>
  );
}

function Preview({ item, index }: { item: QueueItem; index: number }) {
  const { t } = useSettings();
  const nav = useNavigate();
  const c = useView<Case>(`cases/${item.app_id}`);
  const [assignOpen, setAssignOpen] = useState(false);
  if (c.isLoading) return <div className="pv"><Skeleton rows={3} height={26} /><div style={{ height: 30 }} /><Skeleton rows={10} /></div>;
  if (c.isError || !c.data) return <ErrorState error={c.error} retry={() => c.refetch()} />;
  const d = c.data;
  const focus = d.findings.find((f) => f.evidence.some((e) => e.bbox))?.evidence[0]?.doc_id || d.documents[0]?.doc_id;
  const doc = d.documents.find((x) => x.doc_id === focus) || d.documents[0];
  const sealed = d.timeline.some((e) => e.type === "letter issued");
  return (
    <div className="pv">
      <div className="pv-head">
        <div>
          <span className="eyebrow" style={{ color: item.due_word === "Today" ? "var(--ret)" : undefined }}>
            {t("Priority")} {index + 1}<span className="sep">·</span>{t("Due")} {item.due_word}</span>
          <h2 style={{ fontSize: 30, marginTop: 8 }}>{d.institute}</h2>
          <div className="meta" style={{ marginTop: 4 }}><span className="mono">{d.app_id}</span><span className="sep">·</span>{t("Permanent Id")} <span className="mono">{d.permanent_id}</span><span className="sep">·</span>{d.place}</div>
        </div>
        <div className="actions">
          <div style={{ position: "relative" }}>
            <button className="btn" onClick={() => setAssignOpen(!assignOpen)} aria-expanded={assignOpen}>{t("Assign")}</button>
            {assignOpen && <AssignMenu appId={d.app_id} onClose={() => setAssignOpen(false)} />}
          </div>
          <button className="btn" onClick={() => nav(`/case/${d.app_id}`)}>{t("Open full case")}</button>
          <button className="btn primary" onClick={() => nav(d.lane === "return_for_rectification" ? `/case/${d.app_id}/letter` : `/case/${d.app_id}`)}>
            {d.action}<Icon name="arrow_forward" /></button>
        </div>
      </div>
      <div className="strip" style={{ marginTop: 16, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
        <LaneChip lane={d.lane} text={d.lane_label} /><TrustBar score={d.trust.score} /><ChecklistCounts c={d.checklist} /><AppealText c={d} />
      </div>
      <div className="pv-body">
        <div>
          <div className="doc-title"><b>{doc?.label}</b><span className="muted">{t("page")} 1 {t("of")} {doc?.pages}</span></div>
          <DocViewer src={doc?.page_urls[0]} boxes={doc ? boxesFor(d, doc.doc_id) : []} height={430} />
          <p className="note">{t("Boxes show where Pramaan looked. Red: to return. Orange: to check.")}</p>
        </div>
        <div>
          <h3 className="sec">{t("Why this lane")}</h3>
          {d.findings.length ? d.findings.slice(0, 3).map((f) => <FindingCard key={f.finding_id} appId={d.app_id} f={f} />)
            : <div className="finding"><div className="finding-title">{t("All checks passed.")}</div><div className="finding-reason">{t("Spot check due before batch approval.")}</div></div>}
          <h3 className="sec" style={{ marginTop: 22 }}>{t("Case timeline")}</h3>
          <ChainTimeline events={d.timeline.filter((e) => e.type !== "appeal window")} draft={d.lane === "return_for_rectification" && !sealed} />
        </div>
      </div>
    </div>
  );
}

export function AssignMenu({ appId, onClose }: { appId: string; onClose: () => void }) {
  const { t } = useSettings();
  const o = useView<Officer[]>("officers");
  const act = useActions();
  return (
    <div className="pop" style={{ top: 42, insetInlineEnd: 0, width: 260, padding: "6px 0" }} role="menu">
      <p className="muted" style={{ margin: "4px 14px 6px", fontSize: 12 }}>{t("Assign to an officer")}</p>
      {o.isLoading && <div style={{ padding: 12 }}><Skeleton rows={4} /></div>}
      {o.data?.map((x) => <button key={x.id} role="menuitem" className="menu-item" onClick={async () => { await act.assign(appId, x.id); onClose(); }}>
        <Icon name="person" />{x.name}</button>)}
    </div>
  );
}
