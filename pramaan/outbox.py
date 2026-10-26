"""WK23-20 Notification outbox (MOCK): every letter, reminder and decision becomes a JSON record in data/outbox/ with a fixed
template. Nothing is sent: channel says "email (MOCK)" / "SMS (MOCK)". send() is idempotent per key. OWNER: Aryan."""
from __future__ import annotations

import glob
import json
import os
import re

from .i18n import t
from .util import now_iso

def _box(outbox: str | None) -> str:
    return outbox or os.environ.get("PRAMAAN_OUTBOX", os.path.join("data", "outbox"))       # read at call time (tests)
TEMPLATES = {
    "expiry_reminder": ("Certificate expiring: {doc_type} ({app_id})",
                        "Your {doc_type} for application {app_id} expires on {expires} ({days} days). Please upload a renewed certificate."),
    "lod_issued": ("Letter of Deficiency: {app_id}",
                   "A Letter of Deficiency was issued for application {app_id} on {issued_on}. You may respond within 7 days (APH 1.11 a.)."),
    "decision": ("Decision recorded: {app_id}", "A decision was recorded for application {app_id}: {decision}."),
    "loa_draft": ("Letter of Approval (draft): {app_id}",
                  "A Letter of Approval for application {app_id} was drafted after a batch approval with a random spot check. "
                  "It is sent once the competent officer signs it."),
}


def send(kind: str, to: str, data: dict, key: str | None = None, channel: str = "email", outbox: str | None = None,
         lang: str = "en") -> str:
    box = _box(outbox)
    os.makedirs(box, exist_ok=True)
    key = re.sub(r"[^A-Za-z0-9_.-]+", "_", key or f"{kind}-{data.get('app_id', '')}-{now_iso()}")
    path = os.path.join(box, f"{key}.json")
    if os.path.exists(path):
        return path
    subj, body = TEMPLATES[kind]
    rec = {"id": key, "kind": kind, "channel": f"{channel} (MOCK)", "to": to, "subject": t(subj.format(**data), lang),
           "body": t(body.format(**data), lang), "created_at": now_iso(), "mock": True}
    with open(path, "w") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    return path


def log(outbox: str | None = None) -> list[dict]:
    return sorted((json.load(open(p)) for p in glob.glob(os.path.join(_box(outbox), "*.json"))), key=lambda r: r["created_at"])
