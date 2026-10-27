import { useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { currentMode, demoActions, postJSON, saveDemoActions, type DemoActions } from "./client";

// Officer actions. Live: POST to the API (the engine records and audits them). Demo: kept in this browser only.
const listeners = new Set<() => void>();
let snapshot = demoActions();
function emit(next: DemoActions) {
  snapshot = next; saveDemoActions(next); listeners.forEach((l) => l());
}
export function useDemoActions(): DemoActions {
  return useSyncExternalStore((cb) => { listeners.add(cb); return () => listeners.delete(cb); }, () => snapshot);
}

/** The officer's mark on a finding: "correct" (confirmed), "false alarm" or null. The mark made in this browser shows at once
 * (live: it is also sent to the feedback API; demo: it stays here); otherwise the server's / snapshot's mark. */
export function useVerdicts(findings: { finding_id: string; feedback: string | null }[]): (findingId: string) => string | null {
  const demo = useDemoActions();
  return (id: string) => demo.feedback[id] || findings.find((f) => f.finding_id === id)?.feedback || null;
}

/** Is a letter item ticked? The officer's own tick wins; otherwise Correct ticks it, False alarm unticks it, else the draft default. */
export function useTicks(appId: string, findings: { finding_id: string; feedback: string | null }[]) {
  const demo = useDemoActions();
  const verdict = useVerdicts(findings);
  return (id: string, dflt: boolean) => {
    const own = demo.ticks[appId]?.[id];
    if (own !== undefined) return own;
    const v = verdict(id);
    return v === "correct" ? true : v === "false alarm" ? false : dflt;
  };
}

function withoutTick(appId: string, id: string): DemoActions["ticks"] {
  const rest = { ...(snapshot.ticks[appId] || {}) };
  delete rest[id];
  return { ...snapshot.ticks, [appId]: rest };
}

/** Demo: check a letter sealed in this browser by recomputing the hash of the text that was sealed. */
export async function verifyDemoSeal(appId: string): Promise<boolean> {
  const s = snapshot.sealed[appId];
  return !!s && (await sha6(s.text)) === s.hash;
}

async function sha6(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 12);
}

export function useActions() {
  const qc = useQueryClient();
  const user = "officer.demo";                                  // demo sign-in (portal SSO is designed, not built)
  const live = currentMode() === "live";
  const refresh = (...keys: string[]) => keys.forEach((k) => qc.invalidateQueries({ predicate: (q) => String(q.queryKey[0]).startsWith(k) }));
  return {
    async feedback(appId: string, findingId: string, verdict: "correct" | "false alarm") {
      emit({ ...snapshot, ticks: withoutTick(appId, findingId), feedback: { ...snapshot.feedback, [findingId]: verdict } });   // the letter follows this mark
      if (live) { await postJSON(`cases/${appId}/feedback`, { finding_id: findingId, verdict, user }); refresh(`cases/${appId}`, "analytics"); }
    },
    tick(appId: string, findingId: string, on: boolean) {
      emit({ ...snapshot, ticks: { ...snapshot.ticks, [appId]: { ...(snapshot.ticks[appId] || {}), [findingId]: on } } });
    },
    async note(appId: string, text: string) {
      if (live) { await postJSON(`cases/${appId}/notes`, { text, user }); refresh(`cases/${appId}`); return; }
      const list = [...(snapshot.notes[appId] || []), { text, ts: new Date().toISOString(), author: "You (demo)" }];
      emit({ ...snapshot, notes: { ...snapshot.notes, [appId]: list } });
    },
    async assign(appId: string, officer: string) {
      if (live) { await postJSON(`cases/${appId}/assign`, { officer, user }); refresh(`cases/${appId}`, "queue"); return; }
      emit({ ...snapshot, assigned: { ...snapshot.assigned, [appId]: officer } });
    },
    async seal(appId: string, include: string[], text: string, institute?: string): Promise<{ hash: string; seal: string; demo: boolean; file?: string }> {
      if (live) {
        const r = await postJSON<{ file: string; seal: string; issued_hash: string }>(`cases/${appId}/letter/seal`, { include, text, user });
        refresh(`cases/${appId}`, "letters", "appeals", "calendar", "outbox");
        return { hash: r.issued_hash, seal: r.seal, demo: false, file: r.file };
      }
      const hash = await sha6(text);
      emit({ ...snapshot, sealed: { ...snapshot.sealed, [appId]: { hash, ts: new Date().toISOString(), text, institute } } });
      return { hash, seal: "Demo mode: hash of the letter text, kept in this browser. The live app seals it in the audit chain.", demo: true };
    },
    async approveBatch(opened: string[], files: string[]): Promise<{ approved: string[]; error?: string }> {
      if (live) {
        const r = await postJSON<{ approved: string[]; error?: string }>("batch/approve", { opened, user });
        refresh("queue", "batch", "letters", "outbox");
        return r;
      }
      emit({ ...snapshot, approved: [...new Set([...snapshot.approved, ...files])] });
      return { approved: files };
    },
  };
}
