import { useState } from "react";
import { useView } from "../../data/hooks";
import type { Case, Changes as ChangesT } from "../../data/types";
import { useT } from "../../app/settings";
import { Icon } from "../../icons";
import { DemoTag, ErrorState, Skeleton } from "../../components/ui";

// 06 Changes since 2025 (yoy.py + last year's MOCK record). A change alone never moves the file to another lane.
export function Changes({ c }: { c: Case }) {
  const t = useT();
  const v = useView<ChangesT>(`cases/${c.app_id}/changes`);
  const [only, setOnly] = useState(false);
  const rows = (v.data?.rows || []).filter((r) => !only || r.flag);
  return (
    <div className="tabpage">
      <div className="tabpage-head">
        <div><h3>{v.data ? `${v.data.changed} ${t("of")} ${v.data.total} ${t("fields changed since the 2025-26 file")}` : " "}</h3>
          <p>{v.data?.note}</p></div>
        <div className="toggle-group">
          <button className={"btn small" + (only ? " on" : "")} aria-pressed={only} onClick={() => setOnly(true)}>{t("Changed only")}</button>
          <button className={"btn small" + (!only ? " on" : "")} aria-pressed={!only} onClick={() => setOnly(false)}>{t("All fields")}</button>
        </div>
      </div>
      {v.isLoading && <Skeleton rows={8} height={24} />}
      {v.isError && <ErrorState error={v.error} retry={() => v.refetch()} />}
      {v.data && (
        <>
          <table className="table">
            <thead><tr><th>{t("Field")}</th><th>{t("2025-26 file")}</th><th>{c.academic_year} {t("file")}</th><th>{t("Change")}</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.field}><td>{r.field}</td><td>{r.before}</td><td>{r.after}</td>
                <td>{r.flag ? <span className="chip rev"><Icon name="visibility" />{r.change}</span> : <span className="muted">{r.change}</span>}</td></tr>))}</tbody>
          </table>
          {v.data.findings.map((f) => <p key={f.rule_id} className="note"><span className="mono">{f.rule_id}</span>: {f.reason}</p>)}
          <p className="note">{v.data.source.replace(" (demo adapter)", "")} <DemoTag /></p>
        </>
      )}
    </div>
  );
}
