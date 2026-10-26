import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { Icon } from "../icons";
import { useT } from "../app/settings";

// Lane chip: colour + icon + text, always (DESIGN_SYSTEM.md section 5).
const LANE = {
  return_for_rectification: { cls: "ret", icon: "undo", label: "Return for rectification", short: "Return" },
  human_review: { cls: "rev", icon: "visibility", label: "Human review", short: "Review" },
  clear: { cls: "clr", icon: "check_circle", label: "Clear", short: "Clear" },
  not_automated: { cls: "na", icon: "do_not_disturb_on", label: "Not automated", short: "Not automated" },
  info: { cls: "na", icon: "do_not_disturb_on", label: "Not automated", short: "Not automated" },
} as const;
export type Lane = keyof typeof LANE;
export const laneClass = (lane: string) => (LANE[lane as Lane] || LANE.not_automated).cls;
export const laneIcon = (lane: string) => (LANE[lane as Lane] || LANE.not_automated).icon;

export function LaneChip({ lane, text, short }: { lane: string; text?: string; short?: boolean }) {
  const t = useT();
  const l = LANE[lane as Lane] || LANE.not_automated;
  return <span className={`chip ${l.cls}`}><Icon name={l.icon} />{text ?? t(short ? l.short : l.label)}</span>;
}

export function LaneIcon({ lane, size = 16 }: { lane: string; size?: number }) {
  const l = LANE[lane as Lane] || LANE.not_automated;
  return <Icon name={l.icon} size={size} className={`t-${l.cls}`} style={{ fill: `var(--${l.cls})` }} />;
}

export function DemoTag() {
  const t = useT();
  return <span className="tag-demo">{t("demo adapter")}</span>;
}

export function Skeleton({ rows = 6, height = 18, gap = 14 }: { rows?: number; height?: number; gap?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" style={{ display: "grid", gap }}>
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skel" style={{ height, width: `${92 - (i % 3) * 14}%` }} />)}
    </div>
  );
}

export function StateBox({ icon, title, text, action }: { icon: string; title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="state" role="status">
      <Icon name={icon} className="big" style={{ width: 40, height: 40 }} />
      <h3>{title}</h3>
      {text && <p style={{ margin: 0, maxWidth: 420 }}>{text}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const t = useT();
  return <StateBox icon="cloud_off" title={t("This source is not answering")}
    text={`${t("Nothing was changed. Try again in a moment.")} (${String((error as Error)?.message || error).slice(0, 120)})`}
    action={retry && <button className="btn" onClick={retry}><Icon name="refresh" />{t("Try again")}</button>} />;
}

/** The logo mark. Motion B (seal): the gear turns 36 degrees once (900 ms, ease-out) and the badge fills in. */
export function GearMark({ size = 36, spin = false, onDone }: { size?: number; spin?: boolean; onDone?: () => void }) {
  const reduce = useReducedMotion();
  const play = spin && !reduce;
  return (
    <svg viewBox="0 0 400 400" width={size} height={size} role="img" aria-label="Pramaan">
      <motion.g style={{ originX: "200px", originY: "200px" }} initial={{ rotate: 0 }} animate={{ rotate: play ? 36 : 0 }}
        transition={{ duration: play ? 0.9 : 0, ease: "easeOut" }} onAnimationComplete={() => spin && onDone?.()}>
        <path fill="#D4A247" fillRule="evenodd" d="M174.03,36.04 L180.73,8.97 L219.27,8.97 L225.97,36.04 L275.36,52.09 L296.70,34.13 L327.87,56.78 L317.38,82.62 L347.91,124.64 L375.73,122.64 L387.64,159.29 L363.96,174.03 L363.96,225.97 L387.64,240.71 L375.73,277.36 L347.91,275.36 L317.38,317.38 L327.87,343.22 L296.70,365.87 L275.36,347.91 L225.97,363.96 L219.27,391.03 L180.73,391.03 L174.03,363.96 L124.64,347.91 L103.30,365.87 L72.13,343.22 L82.62,317.38 L52.09,275.36 L24.27,277.36 L12.36,240.71 L36.04,225.97 L36.04,174.03 L12.36,159.29 L24.27,122.64 L52.09,124.64 L82.62,82.62 L72.13,56.78 L103.30,34.13 L124.64,52.09 Z M346,200 A146,146 0 1,0 54,200 A146,146 0 1,0 346,200 Z" />
      </motion.g>
      <line x1="289.1" y1="289.1" x2="361.2" y2="361.2" stroke="#F8F7F1" strokeWidth="54" strokeLinecap="round" />
      <line x1="289.1" y1="289.1" x2="361.2" y2="361.2" stroke="#2E5D46" strokeWidth="34" strokeLinecap="round" />
      <circle cx="200" cy="200" r="120" fill="#F8F7F1" stroke="#2E5D46" strokeWidth="24" />
      <path d="M154,130 Q154,124 160,124 L220,124 L246,150 L246,238 Q246,244 240,244 L160,244 Q154,244 154,238 Z" fill="none" stroke="#2E5D46" strokeWidth="10" strokeLinejoin="round" />
      <path d="M220,124 L220,150 L246,150" fill="none" stroke="#2E5D46" strokeWidth="8" strokeLinejoin="round" />
      <line x1="172" y1="168" x2="230" y2="168" stroke="#2E5D46" strokeWidth="9" strokeLinecap="round" />
      <line x1="172" y1="190" x2="230" y2="190" stroke="#2E5D46" strokeWidth="9" strokeLinecap="round" />
      <line x1="172" y1="212" x2="212" y2="212" stroke="#2E5D46" strokeWidth="9" strokeLinecap="round" />
      <circle cx="244" cy="240" r="41" fill="#F8F7F1" />
      <motion.circle cx="244" cy="240" r="34" fill="#D4A247" initial={false}
        animate={{ scale: play ? [0.4, 1] : 1, opacity: play ? [0.3, 1] : 1 }} style={{ originX: "244px", originY: "240px" }}
        transition={{ duration: play ? 0.4 : 0, delay: play ? 0.6 : 0, ease: "easeOut" }} />
      <path d="M229,241 L240,252 L260,229" fill="none" stroke="#FFFFFF" strokeWidth="8.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Loading mark: the gear (motion B), used while a whole page loads. */
export function LoadingMark({ label }: { label?: string }) {
  const t = useT();
  return <div className="state"><GearMark size={44} spin /><p style={{ margin: 0 }}>{label || t("Loading")}</p></div>;
}
