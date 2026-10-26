"""WK23-12 Workload assignment. assign(results, manifests, users) -> {app_id: officer_id}: officers from config/users.yaml
cover regions (`regions`); inside each region the applications go round-robin to its officers, highest priority first.
A region with no officer -> "unassigned". due_date(result, assigned_on, settings) uses assignment_sla_days by lane
(ASSUMPTION). my_queue(...) = one officer's applications, highest priority first. OWNER: Aryan."""
from __future__ import annotations

from datetime import date, timedelta

from .schemas import ApplicationResult


def assign(results: list[ApplicationResult], manifests: dict, users: list[dict]) -> dict:
    officers: dict = {}
    for u in users:
        if u.get("role") == "scrutiny_officer":
            for reg in u.get("regions", []):
                officers.setdefault(reg, []).append(u["id"])
    out, turn = {}, {}
    for r in sorted(results, key=lambda r: (-r.priority, r.app_id)):
        reg = manifests.get(r.app_id, {}).get("declared", {}).get("region")
        team = officers.get(reg, [])
        if not team:
            out[r.app_id] = "unassigned"; continue
        k = turn.get(reg, 0); out[r.app_id] = team[k % len(team)]; turn[reg] = k + 1
    return out


def due_date(result: ApplicationResult, assigned_on: date, settings: dict) -> date:
    return assigned_on + timedelta(days=int((settings.get("assignment_sla_days") or {}).get(result.lane, 5)))


def my_queue(assignments: dict, officer_id: str, results: list[ApplicationResult]) -> list[ApplicationResult]:
    return sorted((r for r in results if assignments.get(r.app_id) == officer_id), key=lambda r: (-r.priority, r.app_id))
