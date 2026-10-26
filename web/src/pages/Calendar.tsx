import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useView } from "../data/hooks";
import type { Calendar as CalT } from "../data/types";
import { useSettings } from "../app/settings";
import { ErrorState, Skeleton, laneClass } from "../components/ui";

// 10 Calendar (expiry.py, appeal.py, due dates): month grid + the next 7 days.
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export function Calendar() {
  const { t } = useSettings();
  const nav = useNavigate();
  const v = useView<CalT>("calendar");
  const today = v.data ? new Date(v.data.today + "T00:00:00") : new Date();
  const [offset, setOffset] = useState(0);
  const grid = useMemo(() => {
    const first = new Date(today.getFullYear(), today.getMonth() + offset, 1);
    const start = new Date(first); start.setDate(1 - ((first.getDay() + 6) % 7));
    return Array.from({ length: 42 }, (_, i) => { const d = new Date(start); d.setDate(start.getDate() + i); return d; });
  }, [v.data, offset]);   // eslint-disable-line react-hooks/exhaustive-deps
  const month = new Date(today.getFullYear(), today.getMonth() + offset, 1);
  const byDay = (d: Date) => (v.data?.events || []).filter((e) => e.date === iso(d));
  return (
    <div className="page">
      <div className="page-head">
        <div><span className="eyebrow">{t("Regulation Bureau")}<span className="sep">·</span>{t("All regions")}</span>
          <h1>{t("Calendar.")}<span className="line2">{v.data ? v.data.headline : " "}</span></h1></div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button className="btn small" onClick={() => setOffset(offset - 1)} aria-label={t("Previous month")}>{"<"}</button>
          <span style={{ minWidth: 120, textAlign: "center", fontWeight: 500 }}>{month.toLocaleDateString("en-GB", { month: "long", year: "numeric" })}</span>
          <button className="btn small" onClick={() => setOffset(offset + 1)} aria-label={t("Next month")}>{">"}</button>
          <button className="btn" onClick={() => setOffset(0)}>{t("Today")}</button>
        </div>
      </div>
      {v.isError && <ErrorState error={v.error} retry={() => v.refetch()} />}
      <div className="cal-wrap">
        <div className="calbox">
          <div className="cal head">{DAYS.map((d) => <div key={d} className="cal-h">{t(d)}</div>)}</div>
          <div className="cal">
          {grid.map((d) => {
            const out = d.getMonth() !== month.getMonth();
            const isToday = iso(d) === v.data?.today;
            return (
              <div key={iso(d)} className={"cal-d" + (out ? " out" : "") + (isToday ? " today" : "")}>
                <span className="cal-n">{d.getDate() === 1 ? d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : d.getDate()}</span>
                {!v.data ? (d.getDate() % 5 === 0 && <div className="skel" style={{ height: 14, marginTop: 6 }} />) : byDay(d).slice(0, 3).map((e, i) => (
                  <button key={i} className={`cal-ev ${laneClass(e.lane)}`} title={`${e.title}${e.detail ? ": " + e.detail : ""}`}
                    onClick={() => e.app_id && nav(`/case/${e.app_id}`)}>{e.kind === "due" ? `${e.app_id} ${t("due")}` : `${e.title}${e.app_id ? ": " + e.app_id : ""}`}</button>
                ))}
                {v.data && byDay(d).length > 3 && <span className="muted" style={{ fontSize: 11 }}>+{byDay(d).length - 3}</span>}
              </div>
            );
          })}
          </div>
        </div>
        <aside>
          <h3 className="sec">{t("Next 7 days")}</h3>
          {!v.data && <Skeleton rows={5} height={40} />}
          {v.data?.next7.map((e, i) => (
            <div key={i} className="next7">
              <span className={e.date === v.data!.today ? "t-ret" : e.lane === "clear" ? "t-clr" : "muted"}>{e.date === v.data!.today ? t("Today")
                : new Date(e.date + "T00:00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric" })}</span>
              <div><b>{e.kind === "due" ? `${e.app_id} ${t("due")}` : e.title}</b><div className="muted" style={{ fontSize: 12.5 }}>{e.detail || e.app_id}</div></div>
            </div>
          ))}
          {v.data && !v.data.next7.length && <p className="muted">{t("Nothing due in the next 7 days.")}</p>}
          <p className="note">{v.data?.note}</p>
        </aside>
      </div>
    </div>
  );
}
