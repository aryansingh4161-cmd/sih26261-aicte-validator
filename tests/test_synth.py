"""Run:  python -m tests.test_synth   (from the repo root). No pytest needed."""
import os, random, tempfile, csv
from pramaan.schemas import VERIFICATION_STATUSES, VERIFICATION_METHODS, Finding, Evidence, BBox
from pramaan.util import parse_date, add_years, similarity
from pramaan.synth import content as C, docs as D
from pramaan.synth.make_dataset import make_one
from pramaan.model import baseline as B, metrics as M


def test_contract_strings():
    assert VERIFICATION_STATUSES == ("verified", "mismatch_detected", "expired", "verification_pending", "source_unavailable", "manual_review_required")
    assert len(VERIFICATION_METHODS) == 6
    f = Finding(finding_id="F1", app_id="A1", source="rule", rule_id="R", title="t", reason="r", severity="low", lane="info")
    assert f.advisory is True
    try:
        Finding(finding_id="F1", app_id="A1", source="rule", rule_id="R", title="t", reason="r", severity="low", lane="info", typo=1)
        raise AssertionError("extra fields must be rejected")
    except Exception as e:
        assert "typo" in str(e) or "extra" in str(e).lower()


def test_dates():
    assert str(parse_date("05-Apr-2025")) == "2025-04-05"
    assert str(parse_date("7 April 2025")) == "2025-04-07"
    assert str(add_years(parse_date("2024-03-04"), 3)) == "2027-03-04"
    assert similarity("A & B Institute", "A AND B INSTITUTE") > 0.99


def test_every_doc_type_and_layout_renders():
    rng = random.Random(1)
    inst = C.make_institute(rng)
    det = D.default_details(rng, inst)
    with tempfile.TemporaryDirectory() as t:
        for dt in D.DOC_TYPES:
            for lay in D.LAYOUTS:
                r = D.render_pdf(dt, lay, inst, det, os.path.join(t, f"{dt}_{lay}.pdf"))
                assert os.path.getsize(r["path"]) > 1000 and r["truth"]


def test_dataset_sample_and_masks():
    with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as tmp:
        rows = [make_one("train", i, t, 1, tmp) for i in range(8)]
        assert any(r["tampered"] == 1 for r in rows) and any(r["tampered"] == 0 for r in rows)
        for r in rows:
            assert os.path.exists(os.path.join(t, r["image"]))
            if r["tampered"]:
                assert os.path.exists(os.path.join(t, r["mask"]))


def test_metrics():
    assert abs(M.auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) - 0.75) < 1e-9
    assert M.auc([0, 1], [0.5, 0.5]) == 0.5


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL TESTS PASSED")
