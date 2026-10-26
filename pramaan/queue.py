"""WK23-4 One-click clear queue with a mandatory spot check.
clear_queue(results) -> applications with lane clear AND no amber checklist row.
spot_sample(app_ids, seed) -> max(1, ceil(10%)) of the batch, seeded (repeatable); the officer must open these first.
approve_batch(log, user, app_ids, opened, seed) -> audit hashes; raises SpotCheckIncomplete until every sampled app is opened.
Each approval row: officer id, reason "auto-cleared, spot-checked k of n", the application's own audit head hash. OWNER: Aryan."""
from __future__ import annotations

import math
import random

from .checklist import tick
from .schemas import ApplicationResult

SPOT_SHARE = 0.10


class SpotCheckIncomplete(Exception):
    pass


def clear_queue(results: list[ApplicationResult]) -> list[ApplicationResult]:
    return [r for r in results if r.lane == "clear" and not any(row["status"] == "amber" for row in tick(r))]


def batch_seed(app_ids: list[str], day: str) -> str:
    return f"{day}|{','.join(sorted(app_ids))}"


def spot_sample(app_ids: list[str], seed: str) -> list[str]:
    ids = sorted(app_ids)
    k = max(1, math.ceil(SPOT_SHARE * len(ids))) if ids else 0
    return sorted(random.Random(seed).sample(ids, k))


def approve_batch(log, user: dict, results: list[ApplicationResult], opened: set[str], seed: str) -> list[str]:
    ids = [r.app_id for r in results]
    sample = spot_sample(ids, seed)
    missing = [a for a in sample if a not in opened]
    if missing:
        raise SpotCheckIncomplete(f"open these applications first: {', '.join(missing)}")
    reason = f"auto-cleared, spot-checked {len(sample)} of {len(ids)}"
    from .outbox import send
    for r in results:
        send("decision", f"institute of {r.app_id}", {"app_id": r.app_id, "decision": "approve for next step"}, key=f"decision-{r.app_id}-{seed[:10]}")
    return [log.append(user["id"], user["role"], "decision: approve for next step (clear-queue batch)", r.app_id,
                       {"reason": reason, "spot_checked": sample, "result_audit_head": r.audit_head_hash, "advisory": True})
            for r in results]
