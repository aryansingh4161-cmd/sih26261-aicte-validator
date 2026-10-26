import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { ROLES, useSettings } from "../app/settings";
import { LANGUAGES } from "../i18n";
import { Icon } from "../icons";
import { GearMark } from "../components/ui";
import { Dropdown } from "./Home";

// 01 Sign in: one screen high, the block centred. Left 40%: sign-in panel; right 60%: motion A (the scan), 4 keyframes:
// 1 Read (0.6 s, then 1.0 s ease-in-out), 2 Check (line at 45%, red box + tag; 0.8 s then 1.0 s), 3 Cross-check (line at 93%,
// green box + tag; 0.8 s then 0.6 s ease-out), 4 Ready for you (lane chip + checklist card; hold 2.4 s), then back to 1.
// Sign-in itself is designed (AICTE portal SSO assumed); here the button goes straight in with the chosen role.
const HOLD = [1600, 1800, 1400, 2400];
const LINE = ["2%", "45%", "93%", "93%"];

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
              <Dropdown label={t("Role")} value={role} onChange={setRole} options={ROLES.map((r) => [r.id, t(r.name)])} /></div>
            <div><div className="field-label">{t("Language")}</div>
              <Dropdown label={t("Language")} value={lang} onChange={setLang} options={LANGUAGES.map((l) => [l.id, l.id === "en" ? "English" : l.native])} /></div>
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
  useEffect(() => {
    if (reduce) { setK(3); return; }
    const id = setTimeout(() => setK((k + 1) % 4), HOLD[k]);
    return () => clearTimeout(id);
  }, [k, reduce]);
  const steps = ["Read", "Check", "Cross-check", "Ready for you"];
  const caption = [t("Reading the documents in APP-07"), t("Checking dates against the Handbook"), t("Cross-checking the seal with the issuing office"),
    t("Ready: 2 things to return, 1 to check")][k];
  const fade = { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: reduce ? 0 : 0.4 } };
  return (
    <section className="signin-right" aria-label={t("How Pramaan checks a file")}>
      <svg className="bg-gear g1" viewBox="0 0 400 400" aria-hidden="true"><circle cx="200" cy="200" r="150" /><circle cx="200" cy="200" r="80" /></svg>
      <svg className="bg-gear g2" viewBox="0 0 400 400" aria-hidden="true"><circle cx="200" cy="200" r="150" /><circle cx="200" cy="200" r="80" /></svg>
      <div className="scan-eyebrow">{t("How Pramaan checks a file")}</div>
      <div className="scan-stage">
        <div className="page-ghost a" /><div className="page-ghost b" />
        <div className="scan-doc">
          <div className="sd-top" /><div className="sd-title" /><div className="sd-seal" />
          {Array.from({ length: 14 }, (_, i) => <div key={i} className="sd-line" style={{ width: i % 4 === 3 ? "50%" : "86%" }} />)}
          <motion.div className="scan-line" animate={{ top: LINE[k] }}
            transition={{ duration: reduce ? 0 : k === 0 ? 1.0 : 1.0, ease: k === 2 ? "easeOut" : "easeInOut", delay: reduce ? 0 : k === 0 ? 0.6 : 0.8 }} />
          <AnimatePresence>
            {k >= 1 && <motion.div key="red" className="sd-box red" {...fade} />}
            {k >= 2 && <motion.div key="green" className="sd-box green" {...fade} />}
          </AnimatePresence>
        </div>
        <AnimatePresence>
          {k >= 1 && <motion.span key="t1" className="sd-tag ret" style={{ top: "44%" }} {...fade}><Icon name="undo" />{t("Expiry date has passed")}</motion.span>}
          {k >= 2 && <motion.span key="t2" className="sd-tag clr" style={{ top: "11%" }} {...fade}><Icon name="check_circle" />{t("Seal matches")}</motion.span>}
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
