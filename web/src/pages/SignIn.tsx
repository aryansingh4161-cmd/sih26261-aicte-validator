import { useEffect, useState } from "react";
import { AnimatePresence, animate, motion, useMotionValue, useMotionValueEvent, useReducedMotion, useTransform } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { ROLES, useSettings } from "../app/settings";
import { LANGUAGES } from "../i18n";
import { Icon } from "../icons";
import { Dropdown, GearMark } from "../components/ui";

// 01 Sign in: one screen high, the block centred. Left 40%: sign-in panel; right 60%: motion A (the scan), 4 keyframes:
// 1 Read (0.6 s, then 1.0 s ease-in-out), 2 Check (beam to 45%, red box + tag; 0.8 s then 1.0 s), 3 Cross-check (beam to 93%,
// green box + tag at the seal; 0.8 s then 0.6 s ease-out), 4 Ready for you (lane chip + checklist card; hold 2.4 s), then back to 1.
// WK27 B1: it reads as scanning: corner brackets frame the page, the beam is the gold line with a translucent band trailing it,
// lines turn from light grey to read ink as the beam passes, a tick appears in the margin of each read line, and each evidence
// box appears when the beam reaches it. Sign-in itself is designed (AICTE portal SSO assumed); the button goes straight in.
const HOLD = [1600, 1800, 1400, 2400];
const MOVE: ([number, number, number, string] | null)[] = [[12, 1.0, 0.6, "easeInOut"], [45, 1.0, 0.8, "easeInOut"], [93, 0.6, 0.8, "easeOut"], null];
const LINES = Array.from({ length: 12 }, (_, i) => ({ y: 21 + i * 4.4, w: i % 4 === 3 ? 48 : i % 3 === 1 ? 78 : 86 }));
const RED = { y0: 41.2, y1: 46.8 }, GREEN = { y0: 77, y1: 92 };

export function SignIn() {
  const { t, role, setRole, lang, setLang, signIn } = useSettings();
  const nav = useNavigate();
  return (
    <div className="signin">
      <section className="signin-left">
        <div className="signin-block">
          <div className="brand"><GearMark size={44} /><div><div className="wordmark" role="img" aria-label="Pramaan AI" style={{ fontSize: 22, margin: 0 }}>Pramaan <b>AI</b></div>
            <div className="tagline">{t("Document verification")}</div></div></div>
          <h1 style={{ fontSize: 34, marginTop: 36 }}>{t("Welcome back.")}<span className="line2">{t("Sign in to start checking.")}</span></h1>
          <p className="muted" style={{ fontSize: 15, lineHeight: 1.55, margin: "20px 0 24px" }}>
            {t("Pramaan AI reads every document in an AICTE approval file, checks it against the Handbook, and shows you what needs a look. You always decide.")}</p>
          <button className="btn primary wide" onClick={() => { signIn(); nav("/"); }}><Icon name="verified_user" />{t("Continue with AICTE portal sign-in")}</button>
          <div className="signin-row">
            <div style={{ flex: 1 }}><div className="field-label">{t("Signing in as")}</div>
              <Dropdown label={t("Role")} showLabel={false} value={role} onChange={setRole} options={ROLES.map((r) => [r.id, t(r.name)])} /></div>
            <div><div className="field-label">{t("Language")}</div>
              <Dropdown label={t("Language")} showLabel={false} value={lang} onChange={setLang} options={LANGUAGES.map((l) => [l.id, l.id === "en" ? "English" : l.native])} /></div>
          </div>
          <p className="note">{t("Uses your existing AICTE portal account. No new password.")}</p>
        </div>
        <footer className="signin-foot muted">{t("AI is advisory. The officer decides.")}
          <a href="#/privacy">{t("Privacy")}</a><span>·</span><a href="#/terms">{t("Terms")}</a><span>·</span><a href="#/accessibility">{t("Accessibility")}</a></footer>
      </section>
      <ScanPanel />
    </div>
  );
}

function ScanPanel() {
  const { t } = useSettings();
  const reduce = useReducedMotion();
  const [k, setK] = useState(reduce ? 3 : 0);
  const beam = useMotionValue(reduce ? 93 : 2);
  const [pos, setPos] = useState(reduce ? 93 : 2);
  useMotionValueEvent(beam, "change", (v) => setPos(v));
  const top = useTransform(beam, (v) => `${v}%`);
  useEffect(() => {
    if (reduce) { setK(3); beam.set(93); setPos(93); return; }
    if (k === 0) { beam.stop(); beam.set(2); setPos(2); }
    const m = MOVE[k];
    if (m) animate(beam, m[0], { duration: m[1], delay: m[2], ease: m[3] as "easeInOut" | "easeOut" });
    const id = setTimeout(() => setK((k + 1) % 4), HOLD[k]);
    return () => clearTimeout(id);
  }, [k, reduce, beam]);
  const steps = ["Read", "Check", "Cross-check", "Ready for you"];
  const caption = [t("Reading the documents in APP-07"), t("Checking dates against the Handbook"), t("Cross-checking the seal with the issuing office"),
    t("Ready: 2 things to return, 1 to check")][k];
  const fade = { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: reduce ? 0 : 0.35 } };
  const red = pos >= (RED.y0 + RED.y1) / 2, green = pos >= GREEN.y1 - 1;          // a box appears once the beam has reached it
  return (
    <section className="signin-right" aria-label={t("How Pramaan checks a file")}>
      <svg className="bg-gear g1" viewBox="0 0 400 400" aria-hidden="true"><circle cx="200" cy="200" r="150" /><circle cx="200" cy="200" r="80" /></svg>
      <svg className="bg-gear g2" viewBox="0 0 400 400" aria-hidden="true"><circle cx="200" cy="200" r="150" /><circle cx="200" cy="200" r="80" /></svg>
      <div className="scan-eyebrow">{t("How Pramaan checks a file")}</div>
      <div className="scan-stage" aria-hidden="true">
        <div className="page-ghost a" /><div className="page-ghost b" />
        <span className="bracket tl" /><span className="bracket tr" /><span className="bracket bl" /><span className="bracket br" />
        <div className="scan-doc">
          <div className={"sd-title" + (pos >= 9 ? " read" : "")} />
          <div className={"sd-sub" + (pos >= 13 ? " read" : "")} />
          {LINES.map((l, i) => (
            <div key={i} className="sd-row" style={{ top: `${l.y}%` }}>
              <span className={"sd-tick" + (pos >= l.y + 1 ? " on" : "")} />
              <span className={"sd-line" + (pos >= l.y + 1 ? " read" : "")} style={{ width: `${l.w}%` }} />
            </div>
          ))}
          <div className={"sd-sign" + (pos >= 86 ? " read" : "")} />
          <div className={"sd-seal" + (pos >= 90 ? " read" : "")} />
          <AnimatePresence>
            {red && <motion.div key="red" className="sd-box red" style={{ top: `${RED.y0}%`, height: `${RED.y1 - RED.y0}%` }} {...fade} />}
            {green && <motion.div key="green" className="sd-box green" style={{ top: `${GREEN.y0}%`, height: `${GREEN.y1 - GREEN.y0}%` }} {...fade} />}
          </AnimatePresence>
          <motion.div className="scan-line" style={{ top }}><span className="beam-band" /></motion.div>
        </div>
        <AnimatePresence>
          {red && <motion.span key="t1" className="sd-tag ret" style={{ top: "41%" }} {...fade}><Icon name="undo" />{t("Expiry date has passed")}</motion.span>}
          {green && <motion.span key="t2" className="sd-tag clr" style={{ top: "80%" }} {...fade}><Icon name="check_circle" />{t("Seal matches")}</motion.span>}
          {k >= 3 && <motion.div key="ck" className="sd-card" {...fade}><div className="muted" style={{ fontSize: 12 }}>{t("Checklist")}</div>
            <div className="t-clr">11 {t("passed")}</div><div className="t-rev">1 {t("to check")}</div><div className="t-ret">2 {t("to return")}</div></motion.div>}
          {k >= 3 && <motion.span key="lane" className="sd-lane" {...fade}><Icon name="undo" />{t("Return for rectification")}</motion.span>}
        </AnimatePresence>
      </div>
      <ol className="scan-steps">{steps.map((s, i) => <li key={s} className={i === k ? "on" : ""}><span>{i + 1}</span>{t(s)}</li>)}</ol>
      <p className="scan-caption" aria-live="polite">{caption}</p>
    </section>
  );
}
