// Shapes of the API views (api/views_*.py). The UI renders them as they come.
export type Box = { x0: number; y0: number; x1: number; y1: number };
export type QueueItem = { app_id: string; institute: string; permanent_id: string; category: string; academic_year: string; place: string;
  region: string; officer: string; trust: number; lane: string; lane_label: string; priority: number; due_by: string; due_word: string;
  headline: string; headline_lane: string };
export type Queue = { role: { id: string; name: string; action: string }; summary: string; count: number; items: QueueItem[] };
export type Doc = { doc_id: string; label: string; doc_type: string; pages: number; status: string; scanned: boolean; page_urls: string[];
  heatmap_urls: Record<string, string> };
export type Finding = { finding_id: string; rule_id: string; title: string; reason: string; lane: string; severity: string; source: string;
  doc_id: string | null; clause: string | null; clause_verified: boolean; evidence: { doc_id: string; page: number; bbox: Box | null }[];
  feedback: string | null };
export type TimelineEvent = { ts: string; actor: string; type: string; hash: string; refs: string[]; note: string };
export type Case = { app_id: string; institute: string; permanent_id: string; category: string; academic_year: string; place: string; lane: string;
  lane_label: string; trust: { score: number; reasons: string[]; label: string };
  checklist: { passed: number; to_check: number; to_return: number; not_automated: number }; assigned: string; due_by: string; due_word: string;
  appeal: { issued_on: string; deadline: string; days_left: number; state: string } | null; notes_count: number; documents: Doc[];
  findings: Finding[]; tamper: { ran: boolean; found: boolean; text: string }; timeline: TimelineEvent[]; action: string };
export type Officer = { id: string; name: string; regions: string[] };
export type Batch = { files: { app_id: string; institute: string }[]; spot: string[]; seed: string; note: string };
