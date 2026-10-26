import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { assetUrl, currentMode } from "../data/client";
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
    <div className="viewer" style={{ maxHeight: height }}>
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

export function FindingCard({ appId, f, compact }: { appId: string; f: Finding; compact?: boolean }) {
  const t = useT();
  const act = useActions();
  const demo = useDemoActions();
  const verdict = currentMode() === "demo" ? demo.feedback[f.finding_id] || f.feedback : f.feedback;
  const [busy, setBusy] = useState(false);
  const mark = async (v: "correct" | "false alarm") => { setBusy(true); try { await act.feedback(appId, f.finding_id, v); } finally { setBusy(false); } };
  return (
    <div className="finding">
      <div className="finding-top">
        <LaneIcon lane={f.lane} size={16} />
        <span className="mono rule">{f.rule_id}</span>
        <span style={{ marginInlineStart: "auto", display: "flex", gap: 6 }}>
          <button className={"btn small" + (verdict === "correct" ? " on" : "")} aria-pressed={verdict === "correct"} disabled={busy} onClick={() => mark("correct")}>{t("Correct")}</button>
          <button className={"btn small" + (verdict === "false alarm" ? " on" : "")} aria-pressed={verdict === "false alarm"} disabled={busy} onClick={() => mark("false alarm")}>{t("False alarm")}</button>
        </span>
      </div>
      <div className="finding-title">{f.title}</div>
      {!compact && <div className="finding-reason">{f.reason}</div>}
    </div>
  );
}

const TL_LABEL: Record<string, string> = { submitted: "Submitted", "auto-checked": "Auto-checked", assigned: "Assigned", "letter issued": "Letter issued",
  resubmitted: "Resubmitted", "EVC pack issued": "Visit pack", decision: "Decision", "appeal window": "Appeal window", closed: "Closed" };
const shortDate = (ts: string) => new Date(ts).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/** Audit-chain timeline. Motion C: a new block slides 8 px into place and its hash appears (300 ms). */
export function ChainTimeline({ events, draft }: { events: TimelineEvent[]; draft?: boolean }) {
  const t = useT();
  const reduce = useReducedMotion();
  return (
    <ol className="chain" aria-label={t("Case timeline")}>
      {events.map((e, i) => (
        <motion.li key={e.type + e.ts} className="block" initial={reduce ? false : { x: -8, opacity: 0 }} animate={{ x: 0, opacity: 1 }}
          transition={{ duration: 0.3, delay: reduce ? 0 : i * 0.05, ease: "easeOut" }}>
          <b>{t(TL_LABEL[e.type] || e.type)}</b><span>{shortDate(e.ts)}</span><span className="mono hash">{e.hash === "-" ? t("derived") : "#" + e.hash.slice(0, 6)}</span>
        </motion.li>
      ))}
      {draft && <li className="block draft"><b>{t("Letter")}</b><span>{t("draft")}</span><span className="mono hash">{t("not sealed")}</span></li>}
    </ol>
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
