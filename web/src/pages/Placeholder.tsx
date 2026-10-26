import { useT } from "../app/settings";
import { Skeleton } from "../components/ui";

export function Placeholder({ name }: { name: string }) {
  const t = useT();
  return <div className="page"><h1>{t(name)}</h1><div style={{ marginTop: 24, maxWidth: 640 }}><Skeleton rows={8} /></div></div>;
}
