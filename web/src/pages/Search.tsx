import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useView } from "../data/hooks";
import { currentMode, postJSON } from "../data/client";
import type { Queue, SearchRes } from "../data/types";
import { useSettings } from "../app/settings";
import { Icon } from "../icons";
import { ErrorState, LaneChip, Skeleton, StateBox } from "../components/ui";

// 14 Search results + saved filters (search.py: fuzzy institute names, rule ids, documents, status words).
// Demo mode has no search engine: it matches the words against the 23 files' names, ids, lanes and headlines in the browser.
const SAVED_KEY = "pramaan.demo.filters";

export function Search() {
  const { t } = useSettings();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const q = params.get("q") || "";
  const live = currentMode() === "live";
  const s = useView<SearchRes>(live ? "search" : null, { q });
  const all = useView<Queue>(live ? null : "queue");
  const [saved, setSaved] = useState<{ name: string; query: string }[]>(() => { try { return JSON.parse(localStorage.getItem(SAVED_KEY) || "[]"); } catch { return []; } });
  const demoRows = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return (all.data?.items || []).filter((i) => words.every((w) => `${i.app_id} ${i.institute} ${i.headline} ${i.lane_label} ${i.region} ${i.permanent_id}`.toLowerCase().includes(w)))
      .map((i) => ({ app_id: i.app_id, institute: i.institute, why: i.headline, lane: i.lane, lane_label: i.lane_label, score: 0 }));
  }, [all.data, q]);
  const rows = live ? s.data?.rows || [] : demoRows;
  const loading = live ? s.isLoading : all.isLoading;
  const save = async () => {
    const name = q || t("All files");
    if (live) { await postJSON("search/filters", { name, query: q, user: "officer.demo" }); s.refetch(); return; }
    const next = [...saved.filter((x) => x.name !== name), { name, query: q }];
    setSaved(next); try { localStorage.setItem(SAVED_KEY, JSON.stringify(next)); } catch { /* blocked storage */ }
  };
  const savedList = live ? (s.data?.saved || []).map((f) => ({ name: f.name, query: f.query, count: f.count })) : saved.map((f) => ({ ...f, count: undefined as number | undefined }));
  return (
    <div className="searchpage">
      <aside className="saved">
        <div className="eyebrow" style={{ color: "var(--muted)", marginBottom: 10 }}>{t("Saved filters")}</div>
        {savedList.map((f) => <button key={f.name} className="menu-item" onClick={() => nav(`/search?q=${encodeURIComponent(f.query)}`)}>
          <Icon name="bookmark" /><span style={{ flex: 1 }}>{f.name}</span>{f.count !== undefined && <span className="muted">{f.count}</span>}</button>)}
        {!savedList.length && <p className="muted" style={{ fontSize: 13 }}>{t("No saved filters yet.")}</p>}
        <button className="btn" style={{ marginTop: 10 }} onClick={save}><Icon name="bookmark" />{t("Save this search")}</button>
      </aside>
      <section className="page" style={{ flex: 1 }}>
        <h2 style={{ fontSize: 28 }}>{rows.length} {rows.length === 1 ? t("result for") : t("results for")} "{q}"</h2>
        {loading && <div style={{ marginTop: 16 }}><Skeleton rows={6} height={26} /></div>}
        {s.isError && <ErrorState error={s.error} retry={() => s.refetch()} />}
        {!loading && !rows.length && <StateBox icon="search" title={t("Nothing matched.")} text={t("Try a Permanent Id, an institute name, a rule id or words like \"expired\", \"missing\" or \"serial\".")} />}
        {rows.length > 0 && (
          <table className="table" style={{ marginTop: 16 }}>
            <thead><tr><th>{t("File")}</th><th>{t("Institute")}</th><th>{t("Why it matched")}</th><th>{t("Lane")}</th></tr></thead>
            <tbody>{rows.map((r) => <tr key={r.app_id} className="clickable" onClick={() => nav(`/case/${r.app_id}`)}>
              <td className="mono">{r.app_id}</td><td>{r.institute}</td><td>{r.why}</td><td><LaneChip lane={r.lane} text={r.lane_label} /></td></tr>)}</tbody>
          </table>
        )}
        <p className="note">{live ? s.data?.note : t("Demo mode: words are matched against file ids, institute names, lanes and headlines in this browser. The live app uses the full search (typos, rule ids, status words).")}</p>
      </section>
    </div>
  );
}
