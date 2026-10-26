"""Extra unit tests for pramaan.rules.run_rules (no pytest)."""
from __future__ import annotations

from datetime import date

from pramaan.rules import run_rules
from pramaan.schemas import Application, DocumentRecord, ExtractedField

RULEPACK = "config/rulepack_eoa_existing.yaml"
TODAY = date(2026, 10, 26)
TEST_SHA256 = "0123456789abcdef" * 4


def field(name: str, value: object) -> ExtractedField:
    """Create an extracted field with its required name."""
    return ExtractedField(name=name, value=value)


def document(
    doc_id: str,
    doc_type: str,
    filename: str,
    fields: dict[str, ExtractedField],
) -> DocumentRecord:
    """Create a document record with all required metadata."""
    return DocumentRecord(
        doc_id=doc_id,
        path=f"tests/fixtures/{filename}",
        sha256=TEST_SHA256,
        doc_type=doc_type,
        filename=filename,
        fields=fields,
    )


def rule_ids(findings) -> set[str]:
    return {finding.rule_id for finding in findings}


def main() -> None:
    app = Application(
        app_id="APP-SYNTH-001",
        permanent_id="1-0000000001",
        category="eoa_existing_regular",
        academic_year="2026-27",
        submitted_on="2026-10-01",
    )

    # 1. No documents -> required missing-document findings.
    f1 = run_rules(app, [], [], None, RULEPACK, TODAY)
    ids1 = rule_ids(f1)
    assert "R-MISS-fire_cert" in ids1, ids1
    assert "R-MISS-affidavit_2" in ids1, ids1

    # 2. Fire certificate valid through 2027-01-01 -> no fire finding.
    fire_ok = document(
        "DOC-FIRE-OK",
        "fire_cert",
        "fire_ok.pdf",
        {"valid_until": field("valid_until", "2027-01-01")},
    )
    f2 = run_rules(app, [fire_ok], [], None, RULEPACK, TODAY)
    assert not any("fire_cert" in (f.rule_id or "") for f in f2), f2

    # 3. Fire certificate expired on 2026-01-01.
    fire_exp = document(
        "DOC-FIRE-EXP",
        "fire_cert",
        "fire_exp.pdf",
        {"valid_until": field("valid_until", "2026-01-01")},
    )
    f3 = run_rules(app, [fire_exp], [], None, RULEPACK, TODAY)
    assert "R-EXP-fire_cert" in rule_ids(f3), f3

    # 4. Invalid date -> low-severity human-review finding.
    fire_bad = document(
        "DOC-FIRE-BAD",
        "fire_cert",
        "fire_bad.pdf",
        {"valid_until": field("valid_until", "31/31/2025")},
    )
    f4 = run_rules(app, [fire_bad], [], None, RULEPACK, TODAY)
    assert any(
        f.doc_id == "DOC-FIRE-BAD"
        and f.severity == "low"
        and f.lane == "human_review"
        for f in f4
    ), f4

    # 5. Structural certificate issued 2022-09-01, valid for 3 years.
    struct_3y = document(
        "DOC-STR-3Y",
        "structural_cert",
        "struct_3y.pdf",
        {
            "issue_date": field("issue_date", "2022-09-01"),
            "validity_years": field("validity_years", "3"),
        },
    )
    f5 = run_rules(app, [struct_3y], [], None, RULEPACK, TODAY)
    assert "R-EXP-structural_cert" in rule_ids(f5), f5

    # 6. Same issue date, but validity is 5 years -> no structural finding.
    struct_5y = document(
        "DOC-STR-5Y",
        "structural_cert",
        "struct_5y.pdf",
        {
            "issue_date": field("issue_date", "2022-09-01"),
            "validity_years": field("validity_years", "5"),
        },
    )
    f6 = run_rules(app, [struct_5y], [], None, RULEPACK, TODAY)
    assert not any(
        "structural_cert" in (f.rule_id or "") for f in f6
    ), f6

    # 7. Old building with no structural certificate -> missing finding.
    f7 = run_rules(
        app, [], [], {"building_completion_date": "1990-01-01"},
        RULEPACK, TODAY,
    )
    assert "R-MISS-structural_cert" in rule_ids(f7), f7

    # 8. Newer building with no structural certificate -> no such finding.
    f8 = run_rules(
        app, [], [], {"building_completion_date": "2015-01-01"},
        RULEPACK, TODAY,
    )
    assert "R-MISS-structural_cert" not in rule_ids(f8), f8

    # 9. TER paid False -> finding; missing TER value -> no R-REC finding.
    f9_false = run_rules(
        app, [], [], {"ter_paid": False}, RULEPACK, TODAY
    )
    assert "R-REC-ter_paid" in rule_ids(f9_false), f9_false

    f9_none = run_rules(app, [], [], None, RULEPACK, TODAY)
    assert not any(
        (f.rule_id or "").startswith("R-REC") for f in f9_none
    ), f9_none

    # 10. Affidavit stamp value 50 -> field finding.
    aff_50 = document(
        "DOC-AFF-50",
        "affidavit_2",
        "affidavit_2.pdf",
        {"stamp_value": field("stamp_value", "50")},
    )
    f10 = run_rules(app, [aff_50], [], None, RULEPACK, TODAY)
    assert "R-FLD-affidavit_2-stamp_value" in rule_ids(f10), f10

    # 11. Other category -> no findings.
    app_other = Application(
        app_id="APP-SYNTH-002",
        permanent_id="1-0000000002",
        category="other",
        academic_year="2026-27",
        submitted_on="2026-10-01",
    )
    f11 = run_rules(
        app_other, [], [], {"ter_paid": False}, RULEPACK, TODAY
    )
    assert f11 == [], f11

    # 12. Missing rule pack -> exactly one configuration-error finding.
    f12 = run_rules(
        app, [], [], None, "config/does_not_exist.yaml", TODAY
    )
    assert len(f12) == 1, f12
    assert f12[0].rule_id == "R-CONFIG-ERROR", f12

    # Required wording check across all generated findings.
    all_findings = (
        f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8
        + f9_false + f9_none + f10 + f11 + f12
    )
    for finding in all_findings:
        assert "reject" not in (finding.title or "").lower(), finding
        assert "reject" not in (finding.reason or "").lower(), finding

    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
