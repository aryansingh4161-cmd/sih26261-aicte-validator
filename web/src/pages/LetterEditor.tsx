import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useView } from "../data/hooks";
import { currentMode } from "../data/client";
import { useActions } from "../data/actions";
import type { Case, LetterFull } from "../data/types";
import { useSettings } from "../app/settings";
import { LANGUAGES } from "../i18n";
import { Icon } from "../icons";
import { ErrorState, GearMark, Skeleton } from "../components/ui";
import { Dropdown } from "./Home";

// 08 Letter editor: an editable Letter of Deficiency with the Handbook quotes; "Seal and issue" adds the hash + QR, puts it in the
// outbox, writes the audit block and starts the 7-day appeal window (letters.save_final + seal.seal_html on the server).
export function LetterEditor({ c }: { c: Case }) {
  const { t, lang } = useSettings();
  const nav = useNavigate();
  const [letterLang, setLetterLang] = useState(lang);
  const v = useView<LetterFull>(`cases/${c.app_id}/letter`, { lang: letterLang });
  const [exclude, setExclude] = useState<string[]>([]);
  const paper = useRef<HTMLDivElement>(null);
  const act = useActions();
  const [sealed, setSealed] = useState<{ hash: string; seal: string; demo: boolean; file?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const defs = useMemo(() => (v.data?.deficiencies || []).filter((d) => !exclude.includes(d.finding_id)), [v.data, exclude]);
  const alreadySealed = c.timeline.some((e) => e.type === "letter issued");
  const seal = async () => {
    if (!paper.current || !v.data) return;
    setBusy(true);
    try {
      const include = v.data.items.filter((i) => i.include && !exclude.includes(i.finding_id)).map((i) => i.finding_id);
      setSealed(await act.seal(c.app_id, include, paper.current.innerText));
    } finally { setBusy(false); }
  };
  return (
    <div className="letterpage">
      <div className="casehead" style={{ borderBottom: "1px solid var(--border)" }}>
        <nav className="crumbs" aria-label={t("Breadcrumb")}><a href="#/">{t("My queue")}</a><Icon name="chevron_right" />
          <a href={`#/case/${c.app_id}`}>{c.app_id}</a><Icon name="chevron_right" /><span>{t("Letter of Deficiency")}</span></nav>
        <div className="casehead-row">
          <div><h1 className="case-title">{t("Letter of Deficiency")}</h1>
            <div className="meta" style={{ fontSize: 13.5 }}>{c.institute}<span className="sep">·</span>{sealed || alreadySealed ? t("Sealed") : t("Draft, not sealed")}</div></div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Dropdown label={t("Letter in")} value={letterLang} onChange={setLetterLang}
              options={LANGUAGES.filter((l) => ["en", "hi", "bn", "ta", "mr"].includes(l.id) || currentMode() === "live").map((l) => [l.id, l.id === "en" ? "English" : l.native])} />
            <button className="btn" onClick={() => window.print()}>{t("Preview PDF")}</button>
            <button className="btn primary" disabled={busy || !!sealed || !defs.length} onClick={seal}>{t("Seal and issue")}<Icon name="verified_user" /></button>
          </div>
        </div>
      </div>
      <div className="letterbody">
        <div className="desk-area">
          {v.isLoading && <div className="letter-paper"><Skeleton rows={14} /></div>}
          {v.isError && <ErrorState error={v.error} retry={() => v.refetch()} />}
          {v.data && (
            <div className="letter-paper" ref={paper} contentEditable={!sealed} suppressContentEditableWarning spellCheck lang={letterLang}
              aria-label={t("Letter text, editable")} role="textbox" aria-multiline="true">
              <div className="lp-row"><span>F. No. <mark>{v.data.header.file_no}</mark></span><span>{t("Date")}: <mark>{v.data.header.date}</mark></span></div>
              <p>{t("To")}<br />{t("The Principal")}<br />{v.data.header.institute}<br />{v.data.header.address}</p>
              <p><b>{t("Subject")}: {v.data.header.subject}</b></p>
              <p>{t("Sir / Madam,")}<br />{t("On scrutiny of the documents submitted for Extension of Approval")} {v.data.header.academic_year}, {t("the following deficiencies were found:")}</p>
              <ol>{defs.map((d) => (
                <li key={d.finding_id}>
                  <p>{d.what}. {d.reason} {d.to_submit}</p>
                  {d.clause && <blockquote>{t("Handbook")}: "{d.clause}"{d.clause_check.found ? ` (p. ${d.clause_check.page}, ${t("checked word for word against the Handbook text")})` : ` (${t("not verified against the Handbook text")})`}</blockquote>}
                </li>))}</ol>
              {!defs.length && <p className="muted">{t("No deficiency is selected for this letter.")}</p>}
              <p>{v.data.closing}</p>
              <p><b>{v.data.signature[0]}</b><br /><b>{v.data.signature[1]}</b></p>
              <p className="muted" style={{ fontSize: 12 }}>{t("Draft prepared by Pramaan (advisory). To be reviewed and signed by the competent officer.")}</p>
            </div>
          )}
        </div>
        <aside className="sidecol">
          {sealed ? <SealResult r={sealed} appId={c.app_id} onBack={() => nav(`/case/${c.app_id}`)} /> : (
            <>
              <h3 className="sec">{t("In this letter")}</h3>
              {v.data?.items.map((i) => {
                const on = i.include && !exclude.includes(i.finding_id);
                return (
                  <label key={i.finding_id} className="incl">
                    <input type="checkbox" checked={on} disabled={!i.include && i.lane === "human_review"}
                      onChange={() => setExclude(on ? [...exclude, i.finding_id] : exclude.filter((x) => x !== i.finding_id))} />
                    <span><span className="incl-title">{i.title}{i.lane === "human_review" && ` (${t("to check, not in letter")})`}</span>
                      <span className="mono muted" style={{ fontSize: 11.5 }}>{i.rule_id}</span></span>
                  </label>
                );
              })}
              {v.data && <div className="infobox"><b>{t("Handbook quotes")}</b>
                <p>{t("Every quote is matched word for word against the Handbook before it can go in a letter.")} {v.data.quotes.found} {t("of")} {v.data.quotes.total} {t("quotes in the rule pack match")} ({t("measured")}).</p></div>}
              <div className="infobox plain"><b><Icon name="verified_user" style={{ color: "var(--brand)" }} /> {t("What \"Seal and issue\" does")}</b>
                <p>{t("Adds a hash and a QR code, saves the letter to the outbox, writes an audit block, and starts the 7-day appeal window. A sealed letter cannot be edited.")}</p></div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

function SealResult({ r, appId, onBack }: { r: { hash: string; seal: string; demo: boolean; file?: string }; appId: string; onBack: () => void }) {
  const { t } = useSettings();
  const [spun, setSpun] = useState(false);
  return (
    <div className="sealresult" aria-live="polite">
      <GearMark size={64} spin onDone={() => setSpun(true)} />
      <h3 style={{ marginTop: 12 }}>{t("Sealed and issued.")}</h3>
      <p className="mono" style={{ margin: "6px 0" }}>#{r.hash.slice(0, 6)}</p>
      <p className="muted" style={{ fontSize: 13 }}>{r.demo ? t(r.seal) : `${t("Seal check")}: ${r.seal}`}</p>
      {spun && (r.demo ? (
        <ul className="sealsteps">
          <li><Icon name="check_circle" />{t("Hash of the letter text computed in this browser")}</li>
          <li className="muted"><Icon name="do_not_disturb_on" />{t("QR seal, outbox, audit block and appeal window: done by the server in the live app")}</li></ul>
      ) : (
        <ul className="sealsteps">
          <li><Icon name="check_circle" />{t("Hash and QR code added")}</li><li><Icon name="check_circle" />{t("Put in the outbox (demo adapter)")}</li>
          <li><Icon name="check_circle" />{t("Audit block written")}</li><li><Icon name="check_circle" />{t("7-day appeal window started")}</li></ul>
      ))}
      <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
        {r.file && <a className="btn" href={`/api/letters/file/${r.file}`} target="_blank" rel="noreferrer"><Icon name="open_in_new" />{t("Open sealed letter")}</a>}
        <a className="btn" href="#/letters">{t("Letters and outbox")}</a>
        <button className="btn" onClick={onBack}>{t("Back to")} {appId}</button>
      </div>
    </div>
  );
}
