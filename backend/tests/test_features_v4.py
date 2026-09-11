"""Backend tests for iteration 4: candidates, summary, bulk personnel-cards PDF/ZIP."""
import io
import os
import zipfile
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
    return s.get(f"{API}/personnel", timeout=30).json()


@pytest.fixture(scope="session")
def may(s):
    doc = s.get(f"{API}/schedule/2026/5", timeout=30).json()
    if not doc.get("exists"):
        r = s.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 5}, timeout=180)
        assert r.status_code == 200
        return r.json()["schedule"]
    return doc


# ---------------- candidates ----------------
class TestCandidates:
    def test_candidates_shape_and_sort(self, s, may):
        r = s.post(f"{API}/schedule/candidates",
                   json={"yil": 2026, "ay": 5, "tarih": "2026-05-04", "slot": "saglikci_2"}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "adaylar" in j
        adaylar = j["adaylar"]
        assert len(adaylar) > 0
        # only saglikci/saglikci_surucu types for saglikci_2
        for c in adaylar:
            assert c["personel_turu"] in ("saglikci", "saglikci_surucu")
            for k in ("personel_id", "ad_soyad", "uygun", "mesaj", "mevcut",
                      "tercih_uyarisi", "saat", "hedef_saat", "onerilen"):
                assert k in c, f"missing {k} in {c}"
        # sorted: uygun first
        uygun_flags = [c["uygun"] for c in adaylar]
        assert uygun_flags == sorted(uygun_flags, key=lambda v: not v), "uygun should be sorted first"
        # at most 3 onerilen
        onerilen_ct = sum(1 for c in adaylar if c["onerilen"])
        assert onerilen_ct <= 3, f"got {onerilen_ct} onerilen"
        # current holder mevcut=true (if slot filled)
        day = next(g for g in may["gunler"] if g["tarih"] == "2026-05-04")
        current = day.get("saglikci_2")
        if current:
            mevcut = [c for c in adaylar if c["mevcut"]]
            assert len(mevcut) == 1
            assert mevcut[0]["personel_id"] == current

    def test_candidates_surucu_24_only_saglikci_surucu(self, s):
        r = s.post(f"{API}/schedule/candidates",
                   json={"yil": 2026, "ay": 5, "tarih": "2026-05-04", "slot": "surucu_24"}, timeout=30)
        assert r.status_code == 200
        for c in r.json()["adaylar"]:
            assert c["personel_turu"] == "saglikci_surucu"

    def test_candidates_404_no_schedule(self, s):
        r = s.post(f"{API}/schedule/candidates",
                   json={"yil": 2027, "ay": 3, "tarih": "2027-03-01", "slot": "saglikci_1"}, timeout=30)
        assert r.status_code == 404


# ---------------- summary ----------------
class TestSummary:
    def test_summary_shape_clean(self, s, may):
        r = s.get(f"{API}/schedule/2026/5/summary", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert j["exists"] is True
        assert j["gun_sayisi"] == 31
        for k in ("hard", "soft", "bos_gorevler", "yoksayilan_istek_sayisi", "updated_at"):
            assert k in j
        assert isinstance(j["hard"], list)
        assert isinstance(j["soft"], list)

    def test_summary_hard_after_leave(self, s, may):
        target = next(g for g in may["gunler"] if g.get("saglikci_1"))
        pid = target["saglikci_1"]
        tarih = target["tarih"]
        s.post(f"{API}/leaves/bulk",
               json={"personel_id": pid, "tarihler": [tarih], "durum": "yillik_izin"}, timeout=30)
        try:
            j = s.get(f"{API}/schedule/2026/5/summary", timeout=30).json()
            hard = j["hard"]
            match = [x for x in hard if x["tarih"] == tarih and x["slot"] == "saglikci_1"]
            assert match, f"expected hard on {tarih}/saglikci_1: {hard}"
            assert "Yıllık izin" in match[0]["mesaj"]
        finally:
            s.post(f"{API}/leaves/bulk",
                   json={"personel_id": pid, "tarihler": [tarih], "durum": None}, timeout=30)

    def test_summary_not_exists(self, s):
        r = s.get(f"{API}/schedule/2027/3/summary", timeout=30)
        assert r.status_code == 200
        assert r.json() == {"exists": False}


# ---------------- bulk personnel cards ----------------
class TestBulkCards:
    def test_bulk_pdf(self, s, may):
        r = s.get(f"{API}/schedule/2026/5/personnel-cards/export/pdf", timeout=120)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 1000

    def test_bulk_zip(self, s, may):
        r = s.get(f"{API}/schedule/2026/5/personnel-cards/export/zip", timeout=120)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/zip")
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        # Count assigned personnel
        assigned = {a["personel_id"] for a in may["assignments"]}
        assert len(names) == len(assigned), f"{len(names)} pdfs vs {len(assigned)} assigned"
        # Each should be PDF
        for n in names:
            data = zf.read(n)
            assert data.startswith(b"%PDF"), f"{n} not a pdf"

    def test_bulk_pdf_404(self, s):
        r = s.get(f"{API}/schedule/2027/3/personnel-cards/export/pdf", timeout=30)
        assert r.status_code == 404

    def test_bulk_zip_404(self, s):
        r = s.get(f"{API}/schedule/2027/3/personnel-cards/export/zip", timeout=30)
        assert r.status_code == 404
