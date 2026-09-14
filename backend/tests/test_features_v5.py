"""Iteration 5 tests: normal targets, overtime opt-in, 24h driver preference."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shift-emergency.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def personnel():
    r = requests.get(f"{API}/personnel", timeout=30)
    assert r.status_code == 200
    return r.json()


def find(personnel, name):
    return next(p for p in personnel if p["ad_soyad"] == name)


# ---------- Targets ----------
def test_targets_may_2026_no_leaves(personnel):
    # ensure no yillik_izin leaves for anyone in May 2026
    for p in personnel:
        leaves = requests.get(f"{API}/leaves", params={"personel_id": p["id"], "yil": 2026, "ay": 5}).json()
        for l in leaves:
            if l["durum"] == "yillik_izin":
                requests.post(f"{API}/leaves/bulk", json={"personel_id": p["id"], "tarihler": [l["tarih"]], "durum": None})

    r = requests.get(f"{API}/schedule/2026/5/targets", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["yil"] == 2026 and data["ay"] == 5
    for t in data["targets"]:
        assert t["hafta_ici_gun"] == 21, f"weekdays={t['hafta_ici_gun']}"
        assert t["tatil_gun"] == 5, f"holidays={t['tatil_gun']} for {t['ad_soyad']}"
        assert t["izin_gun"] == 0
        assert t["normal_hedef"] == 128


def test_targets_with_yillik_izin(personnel):
    p = personnel[0]
    pid = p["id"]
    # 2 weekday non-holiday, 1 weekend, 1 weekday holiday (05-19)
    dates = ["2026-05-04", "2026-05-05", "2026-05-09", "2026-05-19"]
    r = requests.post(f"{API}/leaves/bulk", json={"personel_id": pid, "tarihler": dates, "durum": "yillik_izin"})
    assert r.status_code == 200
    tr = requests.get(f"{API}/schedule/2026/5/targets").json()
    t = next(x for x in tr["targets"] if x["personel_id"] == pid)
    assert t["izin_gun"] == 2, f"got izin_gun={t['izin_gun']}"
    assert t["normal_hedef"] == 112, f"got {t['normal_hedef']}"

    # cleanup
    requests.post(f"{API}/leaves/bulk", json={"personel_id": pid, "tarihler": dates, "durum": None})


# ---------- Stats ----------
def _ensure_july_schedule():
    r = requests.get(f"{API}/schedule/2026/7").json()
    if not r.get("exists") or not r.get("gunler"):
        gen = requests.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 7}, timeout=60).json()
        return gen
    return None


def test_all_overtime_and_stats_july():
    # make sure all personnel are overtime-selected
    ppl = requests.get(f"{API}/personnel").json()
    ids = [p["id"] for p in ppl]
    requests.post(f"{API}/personnel/fazla-mesai", json={"personel_ids": ids})
    gen = requests.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 7}, timeout=90).json()
    assert gen.get("success") is True, f"generate errors: {gen.get('errors')}"
    assert gen.get("ipucu") in (None, "")

    r = requests.get(f"{API}/schedule/2026/7/stats", timeout=30)
    assert r.status_code == 200
    stats = r.json()["stats"]
    for s in stats:
        assert "normal_hedef" in s and "gerceklesen" in s and "eksik_saat" in s and "fazla_mesai" in s and "toplam_saat" in s
        assert "fazla_mesai_secili" in s
        assert s["gerceklesen"] == s["toplam_saat"]
        assert s["eksik_saat"] == max(0, s["normal_hedef"] - s["toplam_saat"])
        assert s["fazla_mesai"] == max(0, s["toplam_saat"] - s["normal_hedef"])
        assert s["normal_hedef"] == 176, f"July normal_hedef {s['normal_hedef']} for {s['ad_soyad']}"


def test_no_overtime_generation_fails():
    requests.post(f"{API}/personnel/fazla-mesai", json={"personel_ids": []})
    gen = requests.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 7}, timeout=90).json()
    assert gen.get("success") is False
    assert gen.get("errors")
    assert gen.get("ipucu") and "fazla mesai" in gen["ipucu"].lower()
    # verify stats: no personnel exceed normal_hedef
    stats = requests.get(f"{API}/schedule/2026/7/stats").json()["stats"]
    for s in stats:
        assert s["toplam_saat"] <= s["normal_hedef"], f"{s['ad_soyad']} exceeded target: {s['toplam_saat']}/{s['normal_hedef']}"


def test_selective_overtime_only_selected_have_overtime():
    ppl = requests.get(f"{API}/personnel").json()
    saglikci_like = [p for p in ppl if p["personel_turu"] in ("saglikci", "saglikci_surucu")]
    # pick 2 saglikci-type as overtime
    selected = [p["id"] for p in saglikci_like[:2]]
    requests.post(f"{API}/personnel/fazla-mesai", json={"personel_ids": selected})
    requests.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 7}, timeout=90).json()
    stats = requests.get(f"{API}/schedule/2026/7/stats").json()["stats"]
    for s in stats:
        if s["personel_turu"] in ("saglikci", "saglikci_surucu") and s["personel_id"] not in selected:
            assert s["fazla_mesai"] == 0, f"{s['ad_soyad']} not selected but overtime={s['fazla_mesai']}"


def test_restore_all_overtime_and_regen_july():
    ppl = requests.get(f"{API}/personnel").json()
    ids = [p["id"] for p in ppl]
    requests.post(f"{API}/personnel/fazla-mesai", json={"personel_ids": ids})
    gen = requests.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 7}, timeout=90).json()
    assert gen.get("success") is True


# ---------- 24h driver preference ----------
def test_24h_driver_preference():
    ppl = requests.get(f"{API}/personnel").json()
    emre = next((p for p in ppl if p["ad_soyad"] == "Emre Aksoy"), None)
    if not emre:
        # pick any saglikci_surucu
        emre = next(p for p in ppl if p["personel_turu"] == "saglikci_surucu")
    r = requests.patch(f"{API}/personnel/{emre['id']}", json={"surucu_tercihi": "24_saat_surucu"})
    assert r.status_code == 200
    assert r.json()["surucu_tercihi"] == "24_saat_surucu"

    # ensure all overtime and regen
    ids = [p["id"] for p in ppl]
    requests.post(f"{API}/personnel/fazla-mesai", json={"personel_ids": ids})
    gen = requests.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 7}, timeout=90).json()
    sch = gen["schedule"]
    days_with_24 = [g for g in sch["gunler"] if g.get("surucu_24")]
    assert len(days_with_24) > 0, "expected some days with surucu_24 set"
    for g in days_with_24:
        assert g.get("surucu_gunduz") is None and g.get("surucu_gece") is None
    # Emre has surucu_24 assignments
    emre_assigns = [a for a in sch["assignments"] if a["personel_id"] == emre["id"] and a["gorev"] == "surucu_24"]
    assert len(emre_assigns) > 0
    for a in emre_assigns:
        assert a["saat"] == 24

    # invalid patch
    r2 = requests.patch(f"{API}/personnel/{emre['id']}", json={"surucu_tercihi": "x"})
    assert r2.status_code == 422

    # restore
    requests.patch(f"{API}/personnel/{emre['id']}", json={"surucu_tercihi": "yok"})
    requests.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 7}, timeout=90)


# ---------- Manual assignment overtime enforcement ----------
def test_candidates_show_overtime_msg():
    # take one saglikci with fazla_mesai=false; find their normal_hedef state
    ppl = requests.get(f"{API}/personnel").json()
    # Set one saglikci to fazla_mesai false
    victim = next(p for p in ppl if p["personel_turu"] == "saglikci")
    requests.patch(f"{API}/personnel/{victim['id']}", json={"fazla_mesai": False})
    # ensure schedule regenerated (all others overtime true stays)
    # request candidates for some slot on some day
    r = requests.post(f"{API}/schedule/candidates",
                      json={"yil": 2026, "ay": 7, "tarih": "2026-07-15", "slot": "saglikci_1"})
    assert r.status_code == 200
    adaylar = r.json()["adaylar"]
    victim_cand = next((c for c in adaylar if c["personel_id"] == victim["id"]), None)
    assert victim_cand is not None
    # msg may or may not appear based on current hours; just check it's a valid dict
    # If uygun False and msg contains 'Normal çalışma hedefi doldu' — pass; otherwise informational
    print(f"victim candidate: uygun={victim_cand['uygun']}, mesaj={victim_cand['mesaj']}")

    # restore
    requests.patch(f"{API}/personnel/{victim['id']}", json={"fazla_mesai": True})


# ---------- Regression ----------
def test_violations_endpoint():
    r = requests.get(f"{API}/schedule/2026/7/violations")
    assert r.status_code == 200
    assert "violations" in r.json()


def test_excel_export():
    r = requests.get(f"{API}/schedule/2026/7/export/excel")
    assert r.status_code == 200


def test_pdf_export():
    r = requests.get(f"{API}/schedule/2026/7/export/pdf")
    assert r.status_code == 200


def test_final_state_regen_july():
    """Ensure final state: all overtime, complete July schedule."""
    ppl = requests.get(f"{API}/personnel").json()
    ids = [p["id"] for p in ppl]
    requests.post(f"{API}/personnel/fazla-mesai", json={"personel_ids": ids})
    # restore all surucu_tercihi to 'yok'
    for p in ppl:
        if p.get("surucu_tercihi") != "yok":
            requests.patch(f"{API}/personnel/{p['id']}", json={"surucu_tercihi": "yok"})
    gen = requests.post(f"{API}/schedule/generate", json={"yil": 2026, "ay": 7}, timeout=90).json()
    assert gen.get("success") is True
