import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { assetUrl } from "../data/client";
import type { Box, Case, Finding, TimelineEvent } from "../data/types";
import { useActions, useDemoActions } from "../data/actions";
import { useT } from "../app/settings";
import { Icon } from "../icons";
import { LaneChip, LaneIcon, laneClass } from "./ui";

/** A document page with evidence boxes (lane colour) and, when there is one, the tamper heatmap. */
export function DocViewer({ src, boxes, heat, showHeat, height = 440 }: { src?: string; boxes: { bbox: Box; lane: string }[]; heat?: string;
  showHeat?: boolean; height?: number }) {
  const t = useT();
  const [broken, setBroken] = useState(false);
  if (!src || broken) {
    return (
      <div className="viewer" style={{ height }}>
        <div className="state"><Icon name="do_not_disturb_on" style={{ width: 32, height: 32 }} />
          <h3>{t("This page could not be shown.")}</h3>
          <p style={{ margin: 0 }}>{t("It is marked \"Not automated\" so it is never passed silently.")}</p></div>
      </div>
    );
  }
  return (
    <div className="viewer" style={{ maxHeight: height }} tabIndex={0} role="region" aria-label={t("Document page, scroll to read")}>
      <div className="paper">
        <img src={assetUrl(src)} alt={t("Document page")} onError={() => setBroken(true)} />
        {showHeat && heat && <img className="heat" src={assetUrl(heat)} alt={t("Tamper heatmap")} />}
        {boxes.map((b, i) => (
          <span key={i} className={`evbox ${laneClass(b.lane)}`} style={{ left: `${b.bbox.x0 * 100}%`, top: `${b.bbox.y0 * 100}%`,
            width: `${(b.bbox.x1 - b.bbox.x0) * 100}%`, height: `${(b.bbox.y1 - b.bbox.y0) * 100}%` }} />
        ))}
      </div>
    </div>
  );
}

export function boxesFor(c: Case, docId: string, page = 1) {
  return c.findings.flatMap((f) => f.evidence.filter((e) => e.doc_id === docId && e.page === page && e.bbox)
    .map((e) => ({ bbox: e.bbox as Box, lane: f.lane })));
}

export function FindingCard({ appId, f, compact, oneLine }: { appId: string; f: Finding; compact?: boolean; oneLine?: boolean }) {
  const t = useT();
  const act = useActions();
  const demo = useDemoActions();
  const verdict = demo.feedback[f.finding_id] || f.feedback;
  const [busy, setBusy] = useState(false);
  const mark = async (v: "correct" | "false alarm") => { setBusy(true); try { await act.feedback(appId, f.finding_id, v); } finally { setBusy(false); } };
  return (
    <div className={"finding" + (verdict === "correct" ? " confirmed" : verdict === "false alarm" ? " dismissed" : "")}>
      <div className="finding-top">
        <LaneIcon lane={f.lane} size={16} />
        <span className="mono rule">{f.rule_id}</span>
        <span style={{ marginInlineStart: "auto", display: "flex", gap: 6 }}>
          <button className={"btn small" + (verdict === "correct" ? " on ok" : "")} aria-pressed={verdict === "correct"} disabled={busy} onClick={() => mark("correct")}>
            {verdict === "correct" && <Icon name="check" />}{t("Correct")}</button>
          <button className={"btn small" + (verdict === "false alarm" ? " on fa" : "")} aria-pressed={verdict === "false alarm"} disabled={busy} onClick={() => mark("false alarm")}>{t("False alarm")}</button>
        </span>
      </div>
      <div className="finding-title">{f.title}</div>
      {!compact && <div className={"finding-reason" + (oneLine ? " one" : "")} title={oneLine ? f.reason : undefined}>{f.reason}</div>}
    </div>
  );
}

export const STEP_LABEL: Record<string, string> = { submitted: "Submitted", "auto-checked": "Auto-checked", assigned: "Assigned",
  "letter issued": "Letter issued", resubmitted: "Resubmitted", "EVC pack issued": "Visit pack", decision: "Decision", "appeal window": "Appeal window",
  closed: "Closed" };
const shortDate = (ts: string) => new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
type Step = { key: string; label: string; state: "done" | "current" | "next"; date?: string; hash?: string };

/** Steps of a file, oldest to newest: what happened (from the audit chain), then where the file is now, then what comes next. */
function chainSteps(events: TimelineEvent[], lane: string): Step[] {
  const has = (type: string) => events.some((e) => e.type === type);
  const appeal = events.find((e) => e.type === "appeal window");
  const appealOpen = !!appeal && appeal.note.toLowerCase().startsWith("open");
  const done: Step[] = events.filter((e) => e.type !== "appeal window" || !appealOpen)
    .map((e) => ({ key: e.type + e.ts, label: STEP_LABEL[e.type] || e.type, state: "done", date: shortDate(e.ts), hash: e.real ? e.hash.slice(0, 6) : undefined }));
  const pending = [...(appealOpen ? ["Appeal window"] : []), ...(!has("letter issued") && lane !== "clear" ? ["Letter"] : []),
    ...(!has("decision") ? ["Decision"] : []), ...(!appeal ? ["Appeal window"] : [])];
  return [...done, ...pending.map((label, i): Step => ({ key: label, label, state: i === 0 ? "current" : "next" }))];
}

/** Audit-chain timeline: circles on a dotted line. Done = brand circle with a check and the date; current = gold ring; next =
 * hollow dashed circle, label only. A hash shows only under a real audit-log block. Motion C: the dotted line draws in once. */
export function ChainTimeline({ events, lane }: { events: TimelineEvent[]; lane: string }) {
  const t = useT();
  const reduce = useReducedMotion();
  const steps = chainSteps(events, lane);
  const n = steps.length;
  const rtl = typeof document !== "undefined" && document.documentElement.dir === "rtl";
  return (
    <div className="chain2">
      <motion.span className="chain2-line" aria-hidden="true" style={{ insetInlineStart: `${50 / n}%`, insetInlineEnd: `${50 / n}%` }}
        initial={reduce ? false : { clipPath: rtl ? "inset(0 0 0 100%)" : "inset(0 100% 0 0)" }} animate={{ clipPath: "inset(0 0% 0 0%)" }}
        transition={{ duration: 0.6, ease: "easeOut" }} />
      <ol aria-label={t("Case timeline")}>
        {steps.map((s) => (
          <li key={s.key} className={"step " + s.state} aria-current={s.state === "current" ? "step" : undefined}>
            <span className="node" aria-hidden="true">{s.state === "done" && <svg viewBox="0 0 16 16"><path d="M4.2 8.3 L6.9 11 L11.8 5.6" /></svg>}</span>
            <span className="step-label" title={t(s.label)}>{t(s.label)}</span>
            {s.date && <span className="step-date">{s.date}</span>}
            {s.hash && <span className="mono step-hash" title={t("Audit-log block")}>#{s.hash}</span>}
            <span className="sr-only">{t(s.state === "done" ? "done" : s.state === "current" ? "now" : "next")}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function TrustBar({ score }: { score: number }) {
  const t = useT();
  const cls = score < 50 ? "ret" : score < 75 ? "rev" : "clr";
  return (
    <span className="trust" title={t("designed score, not a probability")}>
      {t("Trust")} <b className="mono">{score}</b>
      <span className="bar" aria-hidden="true"><span className={cls} style={{ width: `${score}%` }} /></span>
    </span>
  );
}

export function ChecklistCounts({ c }: { c: Case["checklist"] }) {
  const t = useT();
  return (
    <span>{t("Checklist")} <span className="t-clr">{c.passed} {t("passed")}</span>
      {c.to_check > 0 && <><span className="sep">·</span><span className="t-rev">{c.to_check} {t("to check")}</span></>}
      {c.to_return > 0 && <><span className="sep">·</span><span className="t-ret">{c.to_return} {t("to return")}</span></>}
    </span>
  );
}

export function AppealText({ c }: { c: Case }) {
  const t = useT();
  if (!c.appeal) return <span className="muted">{t("Appeal window: not started")}</span>;
  return <span className="muted">{t("Appeal window")}: {c.appeal.state === "open" ? `${c.appeal.days_left} ${t("days left")}` : t(c.appeal.state)}</span>;
}

export { LaneChip };
