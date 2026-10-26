import { useState } from "react";
import { useParams } from "react-router-dom";
import { useView } from "../data/hooks";
import { assetUrl, currentMode, postJSON } from "../data/client";
import type { Evc as EvcT } from "../data/types";
import { useSettings } from "../app/settings";
import { Icon } from "../icons";
import { DemoTag, ErrorState, GearMark, Skeleton, StateBox } from "../components/ui";

// 15 Expert Visit Committee visit pack (evc_pack.py + geo MOCK + photos): what to inspect on site, the committee's answer,
// photos, a map check (demo adapter), print, and a sealed visit report (live).
const ANS = ["Matches", "Differs", "Not seen"];

export function Evc() {
  const { t, mode } = useSettings();
  const { id = "" } = useParams();
  const v = useView<EvcT>(`cases/${id}/evc`);
  const [ans, setAns] = useState<Record<number, string>>({});
  const [done, setDone] = useState<string | null>(null);
  const submit = async () => {
    if (mode === "live") { const r = await postJSON<{ seal: string }>(`cases/${id}/evc/report`, { answers: ans, user: "officer.demo" }); setDone(r.seal); }
    else setDone(t("Demo mode: the answers stay in this browser. The live app seals the report like a letter."));
  };
  if (v.isLoading) return <div className="page"><Skeleton rows={8} height={26} /></div>;
  if (v.isError || !v.data) return <ErrorState error={v.error} retry={() => v.refetch()} />;
  const d = v.data;
  const differs = Object.entries(ans).filter(([, a]) => a === "Differs").map(([i]) => d.rows[Number(i)]?.check);
  return (
    <div className="page">
      <div className="page-head">
        <div><span className="eyebrow">{t("Expert Visit Committee")}<span className="sep">·</span>{t("Visit pack")}</span>
          <h1>{t("Visit pack")}: {d.app_id}.<span className="line2">{d.institute}.</span></h1></div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={() => window.print()}><Icon name="print" />{t("Print pack (PDF)")}</button>
          <button className="btn primary" onClick={submit} disabled={!!done}>{t("Submit visit report")}</button>
        </div>
      </div>
      <div className="evc">
        <div>
          {!d.rows.length ? <StateBox icon="task_alt" title={t("Nothing specific to inspect.")} text={t("Standard inspection only: no finding in this file needs a site check.")} /> : (
            <table className="table">
              <thead><tr><th>{t("On site, check")}</th><th>{t("What the file says")}</th><th>{t("Your answer")}</th><th>{t("Photos")}</th></tr></thead>
              <tbody>{d.rows.map((r, i) => (
                <tr key={i}><td>{r.check}<div className="muted" style={{ fontSize: 11.5 }}>{r.clause}</div></td><td>{r.file_says}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{ANS.map((a) => <button key={a} className={"btn small ans" + (ans[i] === a ? ` on ${a === "Differs" ? "ret" : a === "Matches" ? "clr" : ""}` : "")}
                    aria-pressed={ans[i] === a} onClick={() => setAns({ ...ans, [i]: a })} style={{ marginInlineEnd: 4 }}>{t(a)}</button>)}</td>
                  <td><span className="photos"><Icon name="photo_camera" />{r.photos} {t("photos")}</span></td></tr>))}</tbody>
            </table>)}
          {done && <div className="okbox" style={{ marginTop: 16 }}><GearMark size={28} spin /><div><b>{t("Visit report submitted.")}</b><div style={{ fontSize: 12.5 }}>{done}</div></div></div>}
        </div>
        <aside>
          <div className="mapbox" role="img" aria-label={t("Map check: the declared campus and the address (demo adapter)")}>
            <svg viewBox="0 0 360 240" width="100%" aria-hidden="true">
              <rect width="360" height="240" fill="var(--surface2)" />
              {[60, 150, 260].map((x) => <rect key={x} x={x} y="0" width="10" height="240" fill="var(--surface)" />)}
              {[90, 180].map((y) => <rect key={y} x="0" y={y} width="360" height="10" fill="var(--surface)" />)}
              <circle cx="155" cy="95" r="44" fill="var(--brand)" fillOpacity="0.08" stroke="var(--brand)" strokeDasharray="4 4" />
              <path d="M155 70 c-9 0 -16 7 -16 16 c0 12 16 26 16 26 s16 -14 16 -26 c0 -9 -7 -16 -16 -16z" fill="var(--ret)" />
            </svg>
          </div>
          <p className="note">{d.map.distance_km !== null ? `${t("Address check: the declared campus is")} ${d.map.distance_km < 1 ? `${Math.round(d.map.distance_km * 1000)} m` : `${d.map.distance_km} km`} ${t("from the address")} (${t("map check")}) ` : t("No map check for this address.")} <DemoTag /></p>
          {differs.length > 0 && <div className="box" style={{ borderColor: "var(--ret)" }}><b className="t-ret">{t("Differs")}: {differs.join(", ")}</b></div>}
          {d.photos.length > 0 && <div className="evc-photos">{d.photos.map((p) => <img key={p} src={assetUrl(p)} alt={t("Campus photo")} />)}</div>}
          <p className="note">{d.note}</p>
          {currentMode() === "demo" && <p className="note">{t("Pick an answer per row; nothing is sent in demo mode.")}</p>}
        </aside>
      </div>
    </div>
  );
}
