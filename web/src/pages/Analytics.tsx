import { useState } from "react";
import { useView } from "../data/hooks";
import type { Analytics as AnalyticsT } from "../data/types";
import { useSettings } from "../app/settings";
import { Icon } from "../icons";
import { ErrorState, Skeleton } from "../components/ui";

// 12 Analytics: one layout for every role; the API scopes the figures (officer: my numbers, committees: their stage,
// Executive Committee: all regions). Every number here is synthetic demo data.
// Chart (dataviz): lane = status colour from the design tokens. Return (#B42318) and Human review (#B54708) FAIL the palette
// validator's separation check (dE 6.1 normal, 3.9 deutan), so Human review also carries a 45-degree hatch, segments have 2 px
// gaps, a legend is always shown, each bar has a tooltip, and a table view is one click away.
const SERIES = [
  { key: "clear", label: "Clear", color: "var(--clr)" },
  { key: "human_review", label: "Human review", color: "var(--rev)", hatch: true },
  { key: "return_for_rectification", label: "Return for rectification", color: "var(--ret)" },
] as const;

export function Analytics() {
  const { t } = useSettings();
  const v = useView<AnalyticsT>("analytics");
  const [table, setTable] = useState(false);
  const csv = () => {
    if (!v.data) return;
    const lines = [["region", "files", "clear", "human_review", "returned", "median_days"].join(","),
      ...v.data.regions.map((r) => [r.region, r.files, r.clear, r.review, r.returned, r.median_days ?? ""].join(","))];
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n") + "\n# synthetic demo data\n"], { type: "text/csv" }));
    a.download = "pramaan_analytics_synthetic.csv"; a.click();
  };
  const d = v.data;
  return (
    <div className="page">
      <div className="page-head">
        <div><span className="eyebrow">{d ? d.eyebrow : " "}<span className="sep">·</span>{t("Season 2026-27")}</span>
          <h1>{t("Analytics.")}<span className="line2">{d ? d.headline : " "}</span></h1></div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div className="seg tall" role="group" aria-label={t("Show the weekly figures as")}>
            <button className={!table ? "on" : ""} aria-pressed={!table} onClick={() => setTable(false)}>{t("Chart")}</button>
            <button className={table ? "on" : ""} aria-pressed={table} onClick={() => setTable(true)}>{t("Table")}</button>
          </div>
          <button className="btn" onClick={csv} disabled={!d}><Icon name="download" />{t("Export CSV")}</button>
        </div>
      </div>
      {v.isLoading && <Skeleton rows={8} height={30} />}
      {v.isError && <ErrorState error={v.error} retry={() => v.refetch()} />}
      {d && (
        <>
          <div className="kpis">{d.kpis.map((k) => <div key={k.label}><div className={"kpi" + (k.small ? " small" : "")}>{k.value}</div><div className="muted">{k.label}</div></div>)}</div>
          <div className="an-grid">
            <div className="box">
              <h3>{t("Files by lane, per week of submission")}</h3>
              <ul className="legend">{SERIES.map((s) => <li key={s.key}>{"hatch" in s
                ? <svg width="11" height="11" aria-hidden="true"><defs><pattern id="hatch-l" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <rect width="4" height="4" fill="var(--rev)" /><line x1="0" y1="0" x2="0" y2="4" stroke="var(--surface)" strokeWidth="1.5" /></pattern></defs>
                    <rect width="11" height="11" rx="2" fill="url(#hatch-l)" /></svg>
                : <span className="sw" style={{ background: s.color }} />}{t(s.label)}</li>)}</ul>
              {table ? <WeekTable d={d} /> : <Bars d={d} />}
            </div>
            <div className="box">
              <h3>{t("Top reasons for return")}</h3>
              {d.top.map((x) => (
                <div key={x.title} className="topr"><div className="topr-row"><span>{x.title}</span><span className="mono">{x.count}</span></div>
                  <span className="topr-bar" style={{ width: `${(x.count / Math.max(...d.top.map((y) => y.count))) * 100}%` }} /></div>))}
              {!d.top.length && <p className="muted">{t("No files returned in this scope.")}</p>}
            </div>
          </div>
          <table className="table" style={{ marginTop: 20 }}>
            <thead><tr><th>{t("Region")}</th><th>{t("Files")}</th><th>{t("Clear")}</th><th>{t("Human review")}</th><th>{t("Returned")}</th><th>{t("Median days")}</th></tr></thead>
            <tbody>{d.regions.map((r) => <tr key={r.region}><td>{r.region}</td><td>{r.files}</td><td>{r.clear}</td><td>{r.review}</td><td>{r.returned}</td><td>{r.median_days ?? "-"}</td></tr>)}</tbody>
          </table>
          <p className="note">{d.note}</p>
        </>
      )}
    </div>
  );
}

function Bars({ d }: { d: AnalyticsT }) {
  const { t } = useSettings();
  const [hover, setHover] = useState<number | null>(null);
  const H = 260, BW = 34, GAP = 26, TOP = 10;
  const max = Math.max(1, ...d.weeks.map((w) => w.clear + w.human_review + w.return_for_rectification));
  const W = d.weeks.length * (BW + GAP) + GAP;
  return (
    <div style={{ position: "relative" }}>
      <svg width="100%" height={H + 26} viewBox={`0 0 ${Math.max(W, 640)} ${H + 26}`} preserveAspectRatio="xMinYMax meet" role="img" aria-label={t("Files by lane, per week of submission")}>
        <defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="var(--rev)" /><line x1="0" y1="0" x2="0" y2="6" stroke="var(--surface)" strokeWidth="2" /></pattern></defs>
        <line x1="0" x2={Math.max(W, 640)} y1={H} y2={H} stroke="var(--border)" />
        {d.weeks.map((w, i) => {
          let y = H;
          const x = GAP + i * (BW + GAP);
          return (
            <g key={w.week} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={x - GAP / 2} y={0} width={BW + GAP} height={H} fill="transparent" />
              {SERIES.map((s, j) => {
                const v = w[s.key];
                if (!v) return null;
                const h = ((H - TOP) * v) / max - 2;
                y -= h + 2;
                const isTop = SERIES.slice(j + 1).every((n) => !w[n.key]);
                return <path key={s.key} d={isTop ? `M${x},${y + h} V${y + 4} Q${x},${y} ${x + 4},${y} H${x + BW - 4} Q${x + BW},${y} ${x + BW},${y + 4} V${y + h} Z`
                  : `M${x},${y} H${x + BW} V${y + h} H${x} Z`} fill={"hatch" in s ? "url(#hatch)" : s.color} />;
              })}
              <text x={x + BW / 2} y={H + 18} textAnchor="middle" fontSize="11" fill="var(--muted)">{w.week}</text>
            </g>
          );
        })}
      </svg>
      {hover !== null && (
        <div className="pop tip" style={{ left: `${((GAP + hover * (BW + GAP)) / Math.max(W, 640)) * 100}%`, top: 0 }} role="tooltip">
          <b>{d.weeks[hover].week}</b>{SERIES.map((s) => <div key={s.key}>{t(s.label)}: <span className="mono">{d.weeks[hover][s.key]}</span></div>)}
        </div>
      )}
    </div>
  );
}

function WeekTable({ d }: { d: AnalyticsT }) {
  const { t } = useSettings();
  return (
    <table className="table"><thead><tr><th>{t("Week")}</th>{SERIES.map((s) => <th key={s.key}>{t(s.label)}</th>)}</tr></thead>
      <tbody>{d.weeks.map((w) => <tr key={w.week}><td>{w.week}</td>{SERIES.map((s) => <td key={s.key}>{w[s.key]}</td>)}</tr>)}</tbody></table>
  );
}
