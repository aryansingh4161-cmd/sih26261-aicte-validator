"""WK21 Occupancy / Completion Certificate rules (Handbook R03, R59), no pytest.
  python -m tests.test_occupancy"""
from __future__ import annotations

from pramaan.rules import run_rules
from tests.test_rules_extra import RULEPACK, TODAY, document, field, rule_ids
from pramaan.schemas import Application

APP = Application(app_id="APP-OCC", permanent_id="1-0000000001", category="eoa_existing_regular",
                  academic_year="2026-27", submitted_on="2026-10-01")


def occ(kind: str, issued: str):
    return document("APP-OCC-occupancy_cert", "occupancy_cert", "occupancy_cert.pdf",
                    {"certificate_kind": field("certificate_kind", kind), "issue_date": field("issue_date", issued),
                     "certificate_no": field("certificate_no", "OC/2012/45678")})


def occ_ids(docs) -> set[str]:
    return {r for r in rule_ids(run_rules(APP, docs, [], None, RULEPACK, TODAY)) if "occupancy" in r}


def main() -> None:
    # 1. missing -> R-MISS (high, return_for_rectification, verified R03 clause)
    f = [x for x in run_rules(APP, [], [], None, RULEPACK, TODAY) if x.rule_id == "R-MISS-occupancy_cert"]
    assert len(f) == 1 and f[0].severity == "high" and f[0].lane == "return_for_rectification", f
    assert f[0].clause_verified and "ANNEXURE-2 2.1 iii." in f[0].aph_clause, f
    # 2. full certificate (even 14 years old) -> no occupancy finding
    assert occ_ids([occ("Full", "2012-08-14")]) == set()
    # 3. provisional certificate 3 years old -> R-PROV (medium, human_review, verified R59 clause)
    f = [x for x in run_rules(APP, [occ("Provisional", "2023-10-26")], [], None, RULEPACK, TODAY) if "occupancy" in x.rule_id]
    assert [x.rule_id for x in f] == ["R-PROV-occupancy_cert"] and f[0].lane == "human_review" and f[0].severity == "medium", f
    assert f[0].clause_verified and "ANNEXURE-3 3.1 c." in f[0].aph_clause, f
    # edges: issued in AY 2025-26 -> 2026-27 is its 2nd academic year (accepted); AY 2024-25 -> 3rd (raised); partial too
    assert occ_ids([occ("provisional", "2025-08-01")]) == set()
    assert occ_ids([occ("Provisional", "2024-07-01")]) == {"R-PROV-occupancy_cert"}
    assert occ_ids([occ("Provisional", "2024-06-30")]) == {"R-PROV-occupancy_cert"}       # AY 2023-24 -> 4th year
    assert occ_ids([occ("Partial", "2022-01-10")]) == {"R-PROV-occupancy_cert"}
    assert occ_ids([occ("Provisional", "")]) == set()                                    # date not read -> no claim
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
