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
      if (live) { await postJSON(`cases/${appId}/feedback`, { finding_id: findingId, verdict, user }); refresh(`cases/${appId}`); return; }
      emit({ ...snapshot, feedback: { ...snapshot.feedback, [findingId]: verdict } });
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
    async seal(appId: string, include: string[], text: string): Promise<{ hash: string; seal: string; demo: boolean; file?: string }> {
      if (live) {
        const r = await postJSON<{ file: string; seal: string; issued_hash: string }>(`cases/${appId}/letter/seal`, { include, text, user });
        refresh(`cases/${appId}`, "letters", "appeals", "calendar", "outbox");
        return { hash: r.issued_hash, seal: r.seal, demo: false, file: r.file };
      }
      const hash = await sha6(text);
      emit({ ...snapshot, sealed: { ...snapshot.sealed, [appId]: { hash, ts: new Date().toISOString(), text } } });
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
