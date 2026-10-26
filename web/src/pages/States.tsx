import { useT } from "../app/settings";
import { EmptyQueue, LoadingTable, SourceDown, UnreadableState } from "../components/ui";

// 18 States, all four side by side (the same components the pages use).
export function States() {
  const t = useT();
  return (
    <div className="page">
      <h2>{t("States: when there is nothing, something fails, or it is loading")}</h2>
      <div className="states-grid">
        <div><EmptyQueue text={t("6 clear files were approved today. New files arrive at 9:00.")} /></div>
        <div><UnreadableState what={t("page 2 of the Affidavit")} /></div>
        <div><SourceDown source="DigiLocker" /></div>
        <div style={{ justifyContent: "flex-start" }}><LoadingTable what="APP-07" /></div>
      </div>
    </div>
  );
}
