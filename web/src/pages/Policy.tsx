import { NavLink } from "react-router-dom";
import { useView } from "../data/hooks";
import { useSettings } from "../app/settings";
import { ErrorState, Skeleton } from "../components/ui";

// 17 Privacy / Terms / Accessibility: the docs/*.md texts rendered, with a sub-nav and the site footer (one row).
const DOCS: [string, string][] = [["privacy", "Privacy and data use"], ["terms", "Terms of use"], ["accessibility", "Accessibility statement"]];

function inline(s: string) {                      // **bold** and `code` only; everything else is plain text
  return s.split(/(\*\*[^*\s][^*]*?[^*\s]\*\*|`[^`]+`)/g).map((p, i) => p.startsWith("**") ? <b key={i}>{p.slice(2, -2)}</b>
    : p.startsWith("`") ? <code key={i} className="mono">{p.slice(1, -1)}</code> : p);
}
function Markdown({ text }: { text: string }) {
  const out: JSX.Element[] = [];
  let list: string[] = [];
  let para: string[] = [];
  const flushList = () => { if (list.length) { out.push(<ul key={out.length}>{list.map((l, i) => <li key={i}>{inline(l)}</li>)}</ul>); list = []; } };
  const flushPara = () => { if (para.length) { out.push(<p key={out.length}>{inline(para.join(" "))}</p>); para = []; } };
  for (const line of text.split("\n")) {
    if (/^\s*[-*] /.test(line)) { flushPara(); list.push(line.replace(/^\s*[-*] /, "")); continue; }
    if (/^\s+\S/.test(line) && list.length) { list[list.length - 1] += " " + line.trim(); continue; }
    flushList();
    if (line.startsWith("# ")) { flushPara(); out.push(<h1 key={out.length} style={{ marginBottom: 14 }}>{line.slice(2)}</h1>); }
    else if (line.startsWith("## ")) { flushPara(); out.push(<h3 key={out.length} style={{ fontSize: 19, margin: "22px 0 6px" }}>{line.slice(3)}</h3>); }
    else if (/^\d+\. /.test(line)) { flushPara(); para.push(line); }
    else if (line.trim()) para.push(line.trim());             // a wrapped source line continues the paragraph
    else flushPara();
  }
  flushList(); flushPara();
  return <>{out}</>;
}

export function Policy({ name }: { name: string }) {
  const { t } = useSettings();
  const v = useView<{ markdown: string }>(`docs/${name}`);
  return (
    <div className="policy">
      <div className="policy-main">
        <nav className="policy-nav" aria-label={t("Policies")}>{DOCS.map(([k, l]) => <NavLink key={k} to={`/${k}`} className={({ isActive }) => (isActive ? "on" : "")}>{t(l)}</NavLink>)}</nav>
        <article className="policy-text">
          <span className="eyebrow">{t("Last updated 27 Oct 2026")}<span className="sep">·</span>{t("Draft for review")}</span>
          {v.isLoading && <Skeleton rows={10} />}
          {v.isError && <ErrorState error={v.error} retry={() => v.refetch()} />}
          {v.data && <Markdown text={v.data.markdown} />}
        </article>
      </div>
      <SiteFooter />
    </div>
  );
}

export function SiteFooter() {
  const { t } = useSettings();
  return (
    <footer className="sitefoot">
      <span><span className="wordmark" style={{ fontSize: 15, margin: 0 }}>Pramaan <b>AI</b></span> <span className="muted">{t("Document verification for the AICTE portal")}</span></span>
      <nav aria-label={t("Site")}>{DOCS.map(([k, l]) => <a key={k} href={`#/${k}`}>{t(l)}</a>)}<a href="#/privacy">{t("Help")}</a></nav>
    </footer>
  );
}
