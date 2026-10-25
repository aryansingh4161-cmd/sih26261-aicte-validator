"""CONTRACTS in code. OWNER: Aryan. Everybody imports from here; nobody redefines these shapes.
Coordinates: bbox values are fractions of the page (0..1), origin top-left, so PDFs and images use the same system.
Dates inside field values are ISO strings YYYY-MM-DD."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# The six statuses named in the problem statement (exact strings, do not rename).
VerificationStatus = Literal[
    "verified", "mismatch_detected", "expired",
    "verification_pending", "source_unavailable", "manual_review_required",
]
VERIFICATION_STATUSES = ("verified", "mismatch_detected", "expired",
                         "verification_pending", "source_unavailable", "manual_review_required")

# The six verification methods named in the problem statement.
VerificationMethod = Literal["issuer_portal", "api", "digital_repository",
                             "reference_number", "qr_code", "digital_signature"]
VERIFICATION_METHODS = ("issuer_portal", "api", "digital_repository",
                        "reference_number", "qr_code", "digital_signature")

Severity = Literal["info", "low", "medium", "high"]
# The system never rejects. "clear" = nothing found; the other two are routes to a person.
Lane = Literal["clear", "return_for_rectification", "human_review"]
FindingSource = Literal["rule", "crosscheck", "pdf_forensics", "tamper_model", "photo", "verification"]

DOC_TYPES = ("eoa_letter", "affidavit_2", "noc_format2", "fire_cert", "structural_cert", "area_statement", "unclassified")
CATEGORIES = ("eoa_existing_regular", "intake_increase")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BBox(_Base):
    x0: float
    y0: float
    x1: float
    y1: float


class Evidence(_Base):
    doc_id: str
    page: int = 1                      # 1-based
    bbox: Optional[BBox] = None
    text: str = ""                     # the words the evidence points at (<= 200 chars)


class TextBlock(_Base):
    page: int
    bbox: BBox
    text: str
    source: Literal["text_layer", "ocr"] = "text_layer"
    conf: float = 1.0


class ExtractedField(_Base):
    name: str
    value: Optional[str] = None
    evidence: Optional[Evidence] = None
    confidence: float = 0.0
    method: Literal["text_layer", "ocr", "regex", "table", "manual"] = "regex"


class DocumentRecord(_Base):
    doc_id: str
    filename: str
    path: str
    sha256: str
    slot: Optional[str] = None                 # checklist slot the institute uploaded it under
    doc_type: str = "unclassified"             # one of DOC_TYPES
    doc_type_confidence: float = 0.0
    pages: int = 0
    is_scanned: bool = False                   # True if text layer is (almost) empty
    metadata: Dict[str, Any] = Field(default_factory=dict)   # producer, creator, creation_date, mod_date, eof_markers, has_signature_field, fonts
    blocks: List[TextBlock] = Field(default_factory=list)
    fields: Dict[str, ExtractedField] = Field(default_factory=dict)
    tables: Dict[str, List[Dict[str, str]]] = Field(default_factory=dict)   # e.g. tables["programs"] = [{"course":..,"intake_curr":..}]


class Finding(_Base):
    finding_id: str
    app_id: str
    doc_id: Optional[str] = None               # None for cross-document findings
    source: FindingSource
    rule_id: str
    aph_clause: Optional[str] = None           # clause text as printed in the Handbook, if the rule has one
    clause_verified: bool = False              # True only after a human checked the clause against the PDF
    title: str
    reason: str                                # plain words, one or two sentences
    severity: Severity
    confidence: float = 1.0
    lane: Literal["return_for_rectification", "human_review", "info"]
    evidence: List[Evidence] = Field(default_factory=list)
    advisory: bool = True                      # always True: AI output is decision support


class CompareItem(_Base):
    field: str
    submitted: Optional[str] = None
    returned: Optional[str] = None
    match: bool = False


class VerificationResult(_Base):
    doc_id: str
    method: VerificationMethod
    source: str                                # e.g. "MOCK AICTE records", "pyHanko validation"
    mock: bool = True                          # True unless a real authorised source answered
    timestamp: str                             # ISO 8601
    status: VerificationStatus
    reference: Optional[str] = None
    compared: List[CompareItem] = Field(default_factory=list)
    note: str = ""
    payload_hash: Optional[str] = None


class Alert(_Base):
    alert_id: str
    app_id: str
    kind: Literal["missing_document", "expired_document", "pending_verification",
                  "suspected_anomaly", "mismatch", "source_unavailable"]
    message: str
    created_at: str
    due_by: str                                # SLA date (ISO). SLA lengths are configurable assumptions.
    finding_ids: List[str] = Field(default_factory=list)


class DocSlot(_Base):
    slot: str                                  # e.g. "fire_cert"
    path: str


class Application(_Base):
    """Input manifest for one application (what the institute submitted + what the portal already knows)."""
    app_id: str
    category: str                              # one of CATEGORIES
    academic_year: str                         # "2026-27"
    permanent_id: str                          # AICTE Permanent Id (synthetic in demos)
    submitted_on: str                          # ISO date
    declared: Dict[str, Any] = Field(default_factory=dict)   # latitude, longitude, institute_name ...
    documents: List[DocSlot] = Field(default_factory=list)
    photos: List[str] = Field(default_factory=list)


class ApplicationResult(_Base):
    app_id: str
    category: str
    academic_year: str
    run_at: str
    lane: Lane
    documents: List[DocumentRecord]
    findings: List[Finding]
    verifications: List[VerificationResult]
    alerts: List[Alert]
    audit_head_hash: str
    seconds_taken: float
    notes: List[str] = Field(default_factory=list)
    priority: float = 0.0                      # F10 inspection priority 0..1 (designed weights, ASSUMPTION)
    priority_reasons: List[str] = Field(default_factory=list)
