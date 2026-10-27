"""Shared context for the web API (WK26): paths, loaders, the six Handbook roles and plain-word labels.
No business rules here: every check, score and decision comes from pramaan/. Paths come from the environment so tests and the
snapshot exporter can point the API at their own folders.
  PRAMAAN_OUT (output), PRAMAAN_APPS (data/demo/apps), PRAMAAN_TODAY (ISO date; default: the real date)."""
from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date

import yaml

from pramaan.i18n import t
from pramaan.schemas import ApplicationResult

LANE_LABEL = {"return_for_rectification": "Return for rectification", "human_review": "Human review", "clear": "Clear",
              "not_automated": "Not automated", "info": "Not automated"}
CATEGORY_LABEL = {"eoa_existing_regular": "Extension of Approval", "intake_increase": "Increase in intake"}
DOC_LABEL = {"eoa_letter": "Previous Extension of Approval letter", "affidavit_2": "Affidavit", "noc_format2": "University affiliation letter",
             "fire_cert": "Fire safety certificate", "structural_cert": "Structural stability certificate",
             "area_statement": "Built-up area statement", "occupancy_cert": "Occupancy certificate", "unclassified": "Unread document"}
# The six Handbook roles (DESIGN_DECISIONS.md). The role only changes the summary line, the default queue filter, the main button
# and the analytics scope. Stages are DESIGNED mappings onto the demo data (see docs/FEATURES.md).
ROLES = {
    "regulation_bureau": {"name": "Regulation Bureau", "summary": "{n} files waiting in your region", "stage": "all",
                          "action": "Draft Letter of Deficiency", "scope": "region"},
    "scrutiny": {"name": "Scrutiny / Re-Scrutiny Committee", "summary": "Sent to you for document scrutiny: {n} cases",
                 "stage": "scrutiny", "action": "Record scrutiny result", "scope": "stage"},
    "evc": {"name": "Expert Visit Committee", "summary": "Visits to plan: {n} cases", "stage": "evc", "action": "Open visit pack",
            "scope": "stage"},
    "shc": {"name": "Standing Hearing Committee", "summary": "Forwarded to you by the Regulation Bureau: {n} compliance replies",
            "stage": "shc", "action": "Record recommendation", "scope": "stage"},
    "ec": {"name": "Executive Committee", "summary": "Forwarded to you by the Standing Hearing Committee: {n} cases", "stage": "ec",
           "action": "Record decision", "scope": "stage"},
    "sac": {"name": "Standing Appellate Committee", "summary": "Appeals inside the 7-day window: {n}", "stage": "sac",
            "action": "Hear appeal", "scope": "stage"},
}


@dataclass
class Ctx:
    out: str = field(default_factory=lambda: os.environ.get("PRAMAAN_OUT", "output"))
    apps: str = field(default_factory=lambda: os.environ.get("PRAMAAN_APPS", "data/demo/apps"))
    today: date = field(default_factory=lambda: date.fromisoformat(os.environ["PRAMAAN_TODAY"]) if os.environ.get("PRAMAAN_TODAY") else date.today())
    lang: str = "en"
    role: str = "regulation_bureau"
    user: dict = field(default_factory=lambda: {"id": "officer.demo", "role": "scrutiny_officer", "name": "Demo Scrutiny Officer"})

    @property
    def db(self) -> str:
        return os.path.join(self.out, "audit.db")

    @property
    def outbox(self) -> str:
        """MOCK outbox folder; the API sets PRAMAAN_OUTBOX to this so pramaan.outbox.send() writes to the same place."""
        return os.environ.get("PRAMAAN_OUTBOX", os.path.join(self.out, "outbox"))

    def tr(self, text: str | None) -> str:
        return self.plain(self.year(t(text, self.lang))) if text else (text or "")

    def plain(self, text: str) -> str:
        """No raw internal names on screen (WK27 A4): '(MOCK X)' -> '(X, demo adapter)', 'fire_cert' -> the document's name,
        'institute_name:' -> 'Institute name:'. Display only; the engine's text is unchanged."""
        text = re.sub(r"\(MOCK ([^)]+)\)", lambda m: f"({m.group(1)}, {t('demo adapter', self.lang)})", text)
        text = re.sub(r"\bMOCK ", "", text)
        text = re.sub(r"(?<![-/\w])(" + "|".join(k for k in DOC_LABEL if "_" in k) + r")\b(?![-/.])",
                      lambda m: t(DOC_LABEL[m.group(1)], self.lang).lower() if self.lang == "en" else t(DOC_LABEL[m.group(1)], self.lang), text)
        text = re.sub(r"'([a-z]+(?:_[a-z]+)+)'", lambda m: "'" + t(m.group(1).replace("_", " ").capitalize(), self.lang) + "'", text)
        return re.sub(r"(^|[\s(;])([a-z]+(?:_[a-z]+)+)(?=:)", lambda m: m.group(1) + t(m.group(2).replace("_", " ").capitalize(), self.lang), text)

    def year(self, text: str | None) -> str:
        """Academic year as the screens show it (settings academic_year_shown, WK27 A5; display only)."""
        for a, b in (self.settings().get("academic_year_shown") or {}).items():
            text = (text or "").replace(a, b)
        return text or ""

    def heatmap(self, doc_id: str, n: int) -> str | None:
        """The tamper model writes its heatmaps to output/heatmaps (pramaan/tamper_model.py); look there and in this run's folder."""
        for d in (self.out, "output"):
            p = os.path.join(d, "heatmaps", f"{doc_id}_p{n}.png")
            if os.path.exists(p):
                return p
        return None

    def name(self, actor: str | None) -> str:
        """Display name for an actor id in the audit log (config/users.yaml), never the raw id."""
        names = {u["id"]: u["name"] for u in self.users()}
        names.update({"pramaan-pipeline": "Pramaan (automatic check)", "system": "System", "institute": "Institute"})
        return self.tr(names.get(actor or "", actor or ""))

    def results(self) -> dict[str, ApplicationResult]:
        return {r.app_id: r for r in (ApplicationResult.model_validate_json(open(p).read())
                                      for p in sorted(glob.glob(os.path.join(self.out, "*.result.json"))))}

    def result(self, app_id: str) -> ApplicationResult:
        p = os.path.join(self.out, f"{app_id}.result.json")
        if not os.path.exists(p):
            raise KeyError(app_id)
        return ApplicationResult.model_validate_json(open(p).read())

    def manifests(self) -> dict:
        out = {}
        for p in glob.glob(os.path.join(self.apps, "*.json")):
            m = json.load(open(p)); out[m["app_id"]] = m
        return out

    def manifest(self, app_id: str) -> dict:
        p = os.path.join(self.apps, f"{app_id}.json")
        return json.load(open(p)) if os.path.exists(p) else {}

    def records(self) -> dict:
        p = "data/aicte_records.json"
        return json.load(open(p)) if os.path.exists(p) else {}

    def settings(self) -> dict:
        if not hasattr(self, "_settings"):
            self._settings = yaml.safe_load(open("config/settings.yaml")) or {}
        return self._settings

    def users(self) -> list[dict]:
        return (yaml.safe_load(open("config/users.yaml")) or {}).get("users", [])


def place(address: str | None) -> str:
    """'169 Ring Road, Mockabad, Exampleland South - 233318' -> 'Mockabad, Exampleland South'."""
    parts = [p.strip() for p in (address or "").split(",")]
    return f"{parts[1]}, {parts[2].split(' - ')[0]}" if len(parts) >= 3 else (address or "")


def due_word(due: date, today: date) -> str:
    d = (due - today).days
    return "Overdue" if d < 0 else "Today" if d == 0 else "Tomorrow" if d == 1 else f"{due.day} {due:%b}"


def clean_reason(text: str) -> str:
    """Drop internal file paths from a finding's reason (e.g. 'Heatmap: output/heatmaps/x.png.')."""
    return re.sub(r"\s*Heatmap: \S+\.png\.?", "", text or "")


def initials(name: str) -> str:
    return "".join(w[0] for w in name.replace(".", " ").split()[:2]).upper()
