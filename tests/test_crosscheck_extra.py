"""X-APPID and X-ERROR checks for pramaan.crosscheck (no pytest). Run: python -m tests.test_crosscheck_extra"""
from __future__ import annotations

from datetime import date

from pramaan.crosscheck import run_crosscheck
from pramaan.schemas import Application, DocumentRecord, ExtractedField

TODAY = date(2026, 10, 26)
SHA = "0123456789abcdef" * 4


def doc(doc_id, doc_type, app_id_value):
    fields = {} if app_id_value is None else {"application_id": ExtractedField(name="application_id", value=app_id_value)}
    return DocumentRecord(doc_id=doc_id, path=f"tests/fixtures/{doc_id}.pdf", sha256=SHA, doc_type=doc_type,
                          filename=f"{doc_id}.pdf", fields=fields)


def appid(findings):
    return [f for f in findings if f.rule_id == "X-APPID"]


def main() -> None:
    app = Application(app_id="APP-X", permanent_id="1-0000000001", category="eoa_existing_regular",
                      academic_year="2026-27", submitted_on="2026-10-01")
    same = run_crosscheck(app, [doc("EOA", "eoa_letter", "1-111"), doc("AFF", "affidavit_2", "1-111")], None, TODAY)
    assert len(appid(same)) == 1 and appid(same)[0].lane == "human_review", same
    diff = run_crosscheck(app, [doc("EOA", "eoa_letter", "1-111"), doc("AFF", "affidavit_2", "1-222")], None, TODAY)
    assert not appid(diff), diff
    missing = run_crosscheck(app, [doc("EOA", "eoa_letter", "1-111"), doc("AFF", "affidavit_2", None)], None, TODAY)
    assert not appid(missing), missing
    broken = run_crosscheck(app, [object()], None, TODAY)          # forces the error path
    assert [f.rule_id for f in broken] == ["X-ERROR"] and broken[0].lane == "human_review", broken
    for f in same + diff + missing + broken:
        assert "reject" not in f.title.lower() and "reject" not in f.reason.lower(), f
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
