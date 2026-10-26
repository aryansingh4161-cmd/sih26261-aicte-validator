import type { Case } from "../data/types";
import { useT } from "../app/settings";
import { Skeleton } from "../components/ui";

export function LetterEditor({ c }: { c: Case }) {
  const t = useT();
  return <div className="page"><h1>{t("Letter of Deficiency")}</h1><p className="muted">{c.institute}</p><Skeleton rows={6} /></div>;
}
