"""Backend tests for iteration 3: violations endpoint + personnel card + card PDF."""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    sess.post(f"{API}/seed/demo", timeout=30)
    return sess


@pytest.fixture(scope="session")
def personnel(s):
    r = s.get(f"{API}/personnel", timeout=30)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="session")
def may_schedule(s):
    # Ensure May 2026 exists
    doc = s.get(f"{API}/schedule/2026/5").json()
    if not doc.get("exists"):
        r = s.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 5}, timeout=180)
        assert r.status_code == 200
        return r.json()["schedule"]
    return doc


class TestViolations:
    def test_empty_violations_initially(self, s, may_schedule):
        r = s.get(f"{API}/schedule/2026/5/violations", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "violations" in j
        # Should be empty for a freshly-generated valid schedule
        assert j["violations"] == [], f"unexpected violations: {j['violations']}"

    def test_hard_violation_yillik_izin(self, s, may_schedule, personnel):
        # Find a day/slot with an assigned personnel
        target_day = next(g for g in may_schedule["gunler"] if g.get("saglikci_1"))
        pid = target_day["saglikci_1"]
        tarih = target_day["tarih"]

        # Add yillik_izin for that personnel on that date
        r = s.post(f"{API}/leaves/bulk",
                   json={"personel_id": pid, "tarihler": [tarih], "durum": "yillik_izin"}, timeout=30)
        assert r.status_code == 200
        try:
            v = s.get(f"{API}/schedule/2026/5/violations", timeout=30).json()["violations"]
            match = [x for x in v if x["tarih"] == tarih and x["slot"] == "saglikci_1"]
            assert match, f"no violation for {tarih}/saglikci_1 in {v}"
            assert match[0]["tur"] == "hard"
            assert "Yıllık izin" in match[0]["mesaj"]
        finally:
            s.post(f"{API}/leaves/bulk",
                   json={"personel_id": pid, "tarihler": [tarih], "durum": None}, timeout=30)

    def test_soft_violation_nobet_istemiyor(self, s, may_schedule):
        # find another assigned day (different from previous ideally)
        candidates = [g for g in may_schedule["gunler"] if g.get("saglikci_2")]
        assert candidates
        day = candidates[len(candidates) // 2]  # middle-ish
        pid = day["saglikci_2"]
        tarih = day["tarih"]
        r = s.post(f"{API}/leaves/bulk",
                   json={"personel_id": pid, "tarihler": [tarih], "durum": "nobet_istemiyor"}, timeout=30)
        assert r.status_code == 200
        try:
            v = s.get(f"{API}/schedule/2026/5/violations", timeout=30).json()["violations"]
            match = [x for x in v if x["tarih"] == tarih and x["slot"] == "saglikci_2"]
            assert match, f"no soft violation in {v}"
            assert match[0]["tur"] == "soft"
        finally:
            s.post(f"{API}/leaves/bulk",
                   json={"personel_id": pid, "tarihler": [tarih], "durum": None}, timeout=30)


class TestPersonnelCard:
    def test_card_shape_and_holiday_name(self, s, may_schedule, personnel):
        # Prefer a personnel assigned on 2026-05-01 (Emek ve Dayanışma Günü)
        may1 = next(g for g in may_schedule["gunler"] if g["tarih"] == "2026-05-01")
        pid = may1.get("saglikci_1") or may1.get("saglikci_2") or may1.get("surucu_gunduz") \
            or may1.get("surucu_gece") or may1.get("surucu_24")
        assert pid, "no personnel assigned on 2026-05-01"

        r = s.get(f"{API}/schedule/2026/5/personnel/{pid}/card", timeout=30)
        assert r.status_code == 200
        j = r.json()
        for k in ("personel", "nobetler", "toplam_saat", "toplam_nobet", "mesaj"):
            assert k in j
        assert j["personel"]["id"] == pid
        assert "Mayıs 2026" in j["mesaj"]
        assert j["personel"]["ad_soyad"] in j["mesaj"]
        # entry for 2026-05-01 should have tatil label
        may1_items = [n for n in j["nobetler"] if n["tarih"] == "2026-05-01"]
        assert may1_items
        assert any("Emek" in (n.get("tatil") or "") for n in may1_items), \
            f"expected holiday name for 2026-05-01, got {may1_items}"
        # Weekday of 2026-05-01 is Friday -> "Cum"
        assert may1_items[0]["gun"] == "Cum"
        assert isinstance(j["toplam_saat"], int)
        assert j["toplam_nobet"] == len(j["nobetler"])

    def test_card_pdf_export(self, s, may_schedule, personnel):
        pid = personnel[0]["id"]
        r = s.get(f"{API}/schedule/2026/5/personnel/{pid}/export/pdf", timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 500

    def test_card_pdf_unknown_pid(self, s):
        r = s.get(f"{API}/schedule/2026/5/personnel/does-not-exist/export/pdf", timeout=30)
        assert r.status_code == 404

    def test_card_unknown_pid(self, s):
        r = s.get(f"{API}/schedule/2026/5/personnel/does-not-exist/card", timeout=30)
        assert r.status_code == 404


class TestPdfRegression:
    def test_full_schedule_pdf_still_works(self, s, may_schedule):
        r = s.get(f"{API}/schedule/2026/5/export/pdf", timeout=60)
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")
