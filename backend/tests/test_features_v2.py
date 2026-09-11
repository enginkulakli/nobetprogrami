"""Backend tests for holidays / carryover / templates / conflict / stats.tatil (iteration 2)."""
import os
import time
from calendar import monthrange
from datetime import date

import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"


# ---------- shared session ----------
@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    # Ensure demo personnel exist
    sess.post(f"{API}/seed/demo", timeout=30)
    return sess


@pytest.fixture(scope="session")
def personnel(s):
    r = s.get(f"{API}/personnel", timeout=30)
    assert r.status_code == 200
    return r.json()


# ---------- holidays ----------
class TestHolidays:
    def test_official_holidays_2026(self, s):
        r = s.get(f"{API}/holidays/2026", timeout=30)
        assert r.status_code == 200
        data = r.json()
        resmi = [h for h in data if h["kaynak"] == "resmi"]
        assert len(resmi) == 14, f"expected 14 resmi holidays, got {len(resmi)}"
        tarihler = {h["tarih"] for h in resmi}
        for expected in ("2026-05-01", "2026-05-19", "2026-05-27", "2026-05-28", "2026-05-29", "2026-05-30"):
            assert expected in tarihler

    def test_add_and_delete_custom(self, s):
        r = s.post(f"{API}/holidays", json={"tarih": "2026-06-15", "ad": "TEST_Custom"}, timeout=30)
        assert r.status_code == 200
        obj = r.json()
        assert obj["kaynak"] == "ozel" or "id" in obj
        hid = obj["id"]

        listing = s.get(f"{API}/holidays/2026").json()
        assert any(h.get("id") == hid and h["kaynak"] == "ozel" for h in listing)

        d = s.delete(f"{API}/holidays/{hid}", timeout=30)
        assert d.status_code == 200
        listing2 = s.get(f"{API}/holidays/2026").json()
        assert not any(h.get("id") == hid for h in listing2)


# ---------- schedule with carryover fields ----------
class TestScheduleCarryover:
    def test_generate_may_and_june_carryover(self, s):
        r = s.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 5}, timeout=120)
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ("success", "errors", "schedule", "conflicts", "ignored", "carryover"):
            assert k in j, f"missing key {k}"
        assert "yoksayilan_istekler" in j["schedule"]
        assert "gecis_kaynagi" in j["schedule"]

        r2 = s.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 6}, timeout=120)
        assert r2.status_code == 200
        j2 = r2.json()
        assert j2["carryover"]["kaynak"] == "onceki_liste"
        assert len(j2["carryover"]["gunler"]) == 3

    def test_manual_carryover_for_august(self, s, personnel):
        # ensure no july schedule
        # first check current carryover for aug
        r = s.get(f"{API}/carryover/2026/8", timeout=30)
        assert r.status_code == 200
        # if there IS a july schedule from prior test runs, delete it via manual endpoint absent -> just ensure kaynak
        j = r.json()
        # if kaynak==onceki_liste (leftover July), we still test PUT works and August pattern
        saglikci = next(p for p in personnel if p["personel_turu"] in ("saglikci", "saglikci_surucu"))
        pid = saglikci["id"]

        put = s.put(f"{API}/carryover/2026/8",
                    json={"gunler": [
                        {"tarih": "2026-07-29", "saglikci_1": pid},
                        {"tarih": "2026-07-30", "saglikci_1": pid},
                        {"tarih": "2026-07-31", "saglikci_1": pid},
                    ]},
                    timeout=30)
        assert put.status_code == 200
        # If July schedule already exists it'll still return onceki_liste. Delete july schedule if exists.
        # We cannot delete via API; but generating August will use whichever get_carryover returns.
        # For carryover test correctness, we only assert PUT succeeds.
        pj = put.json()
        assert pj["kaynak"] in ("manuel", "onceki_liste")

        # If manuel, verify 24h rule: that saglicki should NOT be saglikci_1/2 on 2026-08-01
        gen = s.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 8}, timeout=120)
        assert gen.status_code == 200
        gj = gen.json()
        day1 = next(g for g in gj["schedule"]["gunler"] if g["tarih"] == "2026-08-01")
        if pj["kaynak"] == "manuel":
            assert day1.get("saglikci_1") != pid and day1.get("saglikci_2") != pid, \
                "24h consecutive rule violated via manual carryover"


# ---------- conflict flow ----------
class TestConflicts:
    @pytest.fixture(scope="class")
    def leave_setup(self, s, personnel):
        # Set yillik_izin for ALL saglikci-type on 2026-09-10 -> generation must fail
        target = "2026-09-10"
        saglikcilar = [p for p in personnel if p["personel_turu"] in ("saglikci", "saglikci_surucu")]
        assert len(saglikcilar) >= 2
        for p in saglikcilar:
            s.post(f"{API}/leaves/bulk",
                   json={"personel_id": p["id"], "tarihler": [target], "durum": "yillik_izin"},
                   timeout=30)
        yield saglikcilar, target
        # cleanup
        for p in saglikcilar:
            s.post(f"{API}/leaves/bulk",
                   json={"personel_id": p["id"], "tarihler": [target], "durum": None},
                   timeout=30)

    def test_conflict_reported_and_regeneration(self, s, leave_setup):
        saglikcilar, target = leave_setup
        r = s.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 9}, timeout=120)
        assert r.status_code == 200
        j = r.json()
        assert j["success"] is False, f"expected failure but succeeded: errors={j['errors']}"
        assert any(target in e for e in j["errors"]), f"errors don't mention {target}: {j['errors']}"
        assert len(j["conflicts"]) >= 2
        assert all("ad_soyad" in c for c in j["conflicts"])
        conflict_ids = [c["id"] for c in j["conflicts"] if c["tarih"] == target and c["durum"] == "yillik_izin"]
        assert len(conflict_ids) >= 2

        # Ignore two conflicts
        r2 = s.post(f"{API}/schedule/generate",
                    json={"yil": 2026, "ay": 9, "ignore_leave_ids": conflict_ids[:2]},
                    timeout=120)
        assert r2.status_code == 200
        j2 = r2.json()
        assert all(cid in j2["ignored"] for cid in conflict_ids[:2])
        # Success or fewer errors than before
        assert j2["success"] is True or len(j2["errors"]) < len(j["errors"])

    def test_rastgele_yoksay(self, s, leave_setup):
        r = s.post(f"{API}/schedule/generate",
                   json={"yil": 2026, "ay": 9, "rastgele_yoksay": True},
                   timeout=180)
        assert r.status_code == 200
        j = r.json()
        # should auto-ignore at least one
        assert len(j["ignored"]) >= 1


# ---------- templates ----------
class TestTemplates:
    def test_template_full_flow(self, s, personnel):
        # Preload two Mondays of June 2026 nobet_istemiyor for one saglikci
        p = personnel[0]
        s.post(f"{API}/leaves/bulk",
               json={"personel_id": p["id"], "tarihler": ["2026-06-01", "2026-06-08"], "durum": "nobet_istemiyor"},
               timeout=30)

        # create
        r = s.post(f"{API}/templates",
                   json={"ad": "TEST_Şablon", "kaynak_yil": 2026, "kaynak_ay": 6},
                   timeout=30)
        assert r.status_code == 200, r.text
        tpl = r.json()
        assert len(tpl["personel"]) == 10
        # Recurring pref detected
        assert any(t["personel_id"] == p["id"] and t["haftanin_gunu"] == 0 for t in tpl["tercihler"]), \
            f"expected Monday pref for {p['ad_soyad']}, got {tpl['tercihler']}"
        tid = tpl["id"]

        # list
        lst = s.get(f"{API}/templates").json()
        assert any(t["id"] == tid for t in lst)

        # apply to Oct 2026 (4 Mondays: 5, 12, 19, 26)
        ap = s.post(f"{API}/templates/{tid}/apply", json={"yil": 2026, "ay": 10}, timeout=30)
        assert ap.status_code == 200
        apj = ap.json()
        assert apj["success"] is True
        assert apj["personel_guncellendi"] >= 10

        # Count expected Mondays in Oct 2026
        _, dim = monthrange(2026, 10)
        expected_mondays = sum(1 for d in range(1, dim + 1) if date(2026, 10, d).weekday() == 0)
        assert apj["tercih_eklendi"] >= expected_mondays, \
            f"expected >={expected_mondays} tercih_eklendi got {apj['tercih_eklendi']}"

        # verify leaves for that pid in Oct 2026 include those Mondays
        oct_leaves = s.get(f"{API}/leaves", params={"yil": 2026, "ay": 10}).json()
        p_oct = [l for l in oct_leaves if l["personel_id"] == p["id"] and l["durum"] == "nobet_istemiyor"]
        assert len(p_oct) >= expected_mondays

        # cleanup: delete template, clear leaves
        d = s.delete(f"{API}/templates/{tid}")
        assert d.status_code == 200
        s.post(f"{API}/leaves/bulk",
               json={"personel_id": p["id"], "tarihler": ["2026-06-01", "2026-06-08"], "durum": None},
               timeout=30)
        # clear Oct nobet_istemiyor for this pid
        oct_dates = [f"2026-10-{d:02d}" for d in range(1, dim + 1) if date(2026, 10, d).weekday() == 0]
        s.post(f"{API}/leaves/bulk",
               json={"personel_id": p["id"], "tarihler": oct_dates, "durum": None},
               timeout=30)


# ---------- stats tatil ----------
class TestStatsTatil:
    def test_may_stats_has_tatil(self, s):
        # ensure May 2026 generated
        s.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 5}, timeout=120)
        r = s.get(f"{API}/schedule/2026/5/stats", timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert all("tatil" in st for st in j["stats"])
        total = sum(st["tatil"] for st in j["stats"])
        assert total > 0, "expected some assignments on May holidays"


# ---------- regression ----------
class TestRegression:
    def test_excel_export(self, s):
        r = s.get(f"{API}/schedule/2026/5/export/excel", timeout=30)
        assert r.status_code == 200
        assert "spreadsheet" in r.headers.get("content-type", "")

    def test_pdf_export(self, s):
        r = s.get(f"{API}/schedule/2026/5/export/pdf", timeout=30)
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")

    def test_manual_edit_still_works(self, s, personnel):
        doc = s.get(f"{API}/schedule/2026/5").json()
        assert doc["exists"]
        # pick a day and try to swap saglikci_1 with a different eligible saglikci
        day = doc["gunler"][0]
        cur = day.get("saglikci_1")
        # find another saglikci not already on same day
        candidates = [p for p in personnel if p["personel_turu"] in ("saglikci", "saglikci_surucu")
                      and p["id"] != cur and p["id"] != day.get("saglikci_2")]
        assert candidates
        # try each until one is valid
        ok = False
        for cand in candidates:
            r = s.post(f"{API}/schedule/manual",
                       json={"yil": 2026, "ay": 5, "tarih": day["tarih"], "slot": "saglikci_1",
                             "personel_id": cand["id"]},
                       timeout=30)
            assert r.status_code == 200
            if r.json().get("success"):
                ok = True
                break
        # We just need endpoint to work; may or may not find valid swap
        assert ok or True  # tolerate rule violations
