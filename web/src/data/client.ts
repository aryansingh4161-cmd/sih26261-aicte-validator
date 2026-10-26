// One data layer, two back ends (WK26):
//  live: the FastAPI server (/api/..., proxied by Vite in dev);
//  demo: the static snapshot written by tools/export_snapshot.py (public/snapshot/<lang>/<path>.json), actions kept in localStorage.
// No business logic here: the views arrive ready from the engine (live) or from the engine's snapshot (demo).
export type Mode = "live" | "demo";
const BASE = import.meta.env.BASE_URL;
export const SNAP_LANGS = ["en", "hi", "bn", "ta", "mr"];
let mode: Mode = import.meta.env.VITE_DATA_MODE === "demo" ? "demo" : "live";
let probed = mode === "demo";

export async function detectMode(): Promise<Mode> {
  if (probed) return mode;
  probed = true;
  try {
    const r = await fetch("/api/health", { cache: "no-store" });
    mode = r.ok ? "live" : "demo";
  } catch {
    mode = "demo";
  }
  return mode;
}
export const currentMode = () => mode;

/** Demo snapshot path for an API path like "queue" or "cases/APP-07/checklist". */
function snapPath(path: string, lang: string, role: string): string {
  const l = SNAP_LANGS.includes(lang) ? lang : "en";
  if (path === "queue" || path === "analytics") return `${BASE}snapshot/${l}/${path}/${role}.json`;
  if (path.startsWith("docs/")) return `${BASE}snapshot/en/${path}.json`;
  return `${BASE}snapshot/${l}/${path}.json`;
}

export function assetUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  if (mode === "live") return url;
  return url.replace(/^\/api\//, `${BASE}snapshot/img/`);
}

export class HttpError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function getJSON<T>(path: string, opts: { lang: string; role: string; params?: Record<string, string | undefined> }): Promise<T> {
  if (mode === "demo") {
    const r = await fetch(snapPath(path, opts.lang, opts.role));
    if (!r.ok) throw new HttpError(r.status, `not in the demo snapshot: ${path}`);
    return r.json();
  }
  const q = new URLSearchParams({ lang: opts.lang, role: opts.role });
  Object.entries(opts.params || {}).forEach(([k, v]) => v !== undefined && v !== "" && q.set(k, v));
  const r = await fetch(`/api/${path}?${q}`);
  if (!r.ok) throw new HttpError(r.status, (await r.text()).slice(0, 200));
  return r.json();
}

export async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`/api/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new HttpError(r.status, (await r.text()).slice(0, 200));
  return r.json();
}

/** Demo-mode action store: what the officer did in this browser (never sent anywhere). */
const KEY = "pramaan.demo.actions.v1";
export type DemoActions = { feedback: Record<string, string>; notes: Record<string, { text: string; ts: string; author: string }[]>;
  sealed: Record<string, { hash: string; ts: string; text: string }>; approved: string[]; assigned: Record<string, string> };
export function demoActions(): DemoActions {
  try {
    return { feedback: {}, notes: {}, sealed: {}, approved: [], assigned: {}, ...JSON.parse(localStorage.getItem(KEY) || "{}") };
  } catch {
    return { feedback: {}, notes: {}, sealed: {}, approved: [], assigned: {} };
  }
}
export function saveDemoActions(a: DemoActions) {
  try { localStorage.setItem(KEY, JSON.stringify(a)); } catch { /* private mode: actions last for this page only */ }
}
