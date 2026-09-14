"""Zorunlu sürücü minimumları, manuel 12s atama ve aylık liste silme testleri."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import date

import pytest
import requests

sys.path.append(str(Path(__file__).resolve().parents[1]))
from scheduler import generate_schedule, validate_manual_assignment


def _mk_person(pid: str, ad: str, tur: str, **extra):
    base = {
        "id": pid,
        "ad_soyad": ad,
        "personel_turu": tur,
        "aktif": True,
        "hedef_saat": 1000,
        "fazla_mesai": True,
        "surucu_tercihi": "yok",
    }
    base.update(extra)
    return base


def test_mandatory_driver_minimum_blocks_auto_24_until_met_then_allows_it():
    # Senaryo A: 1-15 dönemi minimumları sürekli açık kalsın -> auto surucu_24 kullanılmamalı.
    personnel_pending = [
        _mk_person("s1", "S1", "saglikci"),
        _mk_person("s2", "S2", "saglikci"),
        _mk_person("s3", "S3", "saglikci"),
        _mk_person("s4", "S4", "saglikci"),
        _mk_person("ss1", "SS1", "saglikci_surucu", surucu_tercihi="24_saat_surucu"),
        _mk_person("d1", "D1", "surucu", nobet_hedef_1_15=20),
        _mk_person("d2", "D2", "surucu", nobet_hedef_1_15=20),
        _mk_person("d3", "D3", "surucu"),
        _mk_person("d4", "D4", "surucu"),
    ]
    leaves = {}
    targets = {p["id"]: 1000 for p in personnel_pending}
    schedule_a, errors_a = generate_schedule(2026, 11, personnel_pending, leaves, holidays=set(), targets=targets)
    assert isinstance(errors_a, list)

    first_half_days = [g for g in schedule_a.gunler if date.fromisoformat(g.tarih).day <= 15]
    assert first_half_days, "İlk yarı günleri oluşmalı"
    assert all(g.surucu_24 is None for g in first_half_days), "Minimum açıkken 1-15 döneminde otomatik surucu_24 olmamalı"
    assert all(g.surucu_gunduz and g.surucu_gece for g in first_half_days), "12s sürücü ikilisi mümkünken tamamı dolu olmalı"

    # Senaryo B: minimumlar erken tamamlanabilir -> sonrasında surucu_24 kullanılabilmeli.
    personnel_met = [
        _mk_person("s1", "S1", "saglikci"),
        _mk_person("s2", "S2", "saglikci"),
        _mk_person("s3", "S3", "saglikci"),
        _mk_person("s4", "S4", "saglikci"),
        _mk_person("ss1", "SS1", "saglikci_surucu", surucu_tercihi="24_saat_surucu"),
        _mk_person("ss2", "SS2", "saglikci_surucu", surucu_tercihi="24_saat_surucu"),
        _mk_person("d1", "D1", "surucu", nobet_hedef_1_15=1),
        _mk_person("d2", "D2", "surucu", nobet_hedef_1_15=1),
    ]
    targets_b = {p["id"]: 1000 for p in personnel_met}
    schedule_b, _errors_b = generate_schedule(2026, 11, personnel_met, leaves, holidays=set(), targets=targets_b)
    surucu24_after_day1 = [
        g for g in schedule_b.gunler
        if date.fromisoformat(g.tarih).day > 1 and date.fromisoformat(g.tarih).day <= 15 and g.surucu_24
    ]
    assert surucu24_after_day1, "Minimumlar tamamlandıktan sonra 1-15 döneminde surucu_24 atanabilmeli"


def test_manual_12h_driver_assignment_allows_24_preference_saglikci_surucu():
    personnel = [
        _mk_person("s1", "S1", "saglikci"),
        _mk_person("s2", "S2", "saglikci"),
        _mk_person("ss1", "SS1", "saglikci_surucu", surucu_tercihi="24_saat_surucu"),
        _mk_person("d1", "D1", "surucu"),
    ]
    schedule_doc = {
        "yil": 2026,
        "ay": 11,
        "gunler": [
            {
                "tarih": "2026-11-03",
                "saglikci_1": "s1",
                "saglikci_2": "s2",
                "surucu_gunduz": None,
                "surucu_gece": "d1",
                "surucu_24": None,
            }
        ],
    }
    ok, msg = validate_manual_assignment(
        schedule_doc,
        "2026-11-03",
        "surucu_gunduz",
        "ss1",
        personnel,
        leaves={},
        carryover_days=[],
        targets={p["id"]: 1000 for p in personnel},
    )
    assert ok, f"24s tercihi 12s manuel sürücü atamasını engellememeli, mesaj={msg}"


BASE_URL = os.environ.get("TEST_API_BASE", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"
TEST_STATION_ID = os.environ.get("TEST_STATION_ID", "a53279e3-7d48-49bf-b43a-0d5431d8dee7")


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{API}/auth/login",
        json={"kullanici_adi": "admin", "sifre": "admin123"},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}", "X-Istasyon-Id": TEST_STATION_ID}


def test_delete_schedule_endpoint_removes_only_target_month(admin_headers):
    # Ekim 2026 dokunulmayacak ay; test için Kasım 2026 kullan.
    throwaway_yil, throwaway_ay = 2026, 11

    gen = requests.post(
        f"{API}/schedule/generate",
        json={"yil": throwaway_yil, "ay": throwaway_ay},
        headers=admin_headers,
        timeout=90,
    )
    assert gen.status_code == 200, gen.text

    before = requests.get(
        f"{API}/schedule/{throwaway_yil}/{throwaway_ay}",
        headers=admin_headers,
        timeout=30,
    )
    assert before.status_code == 200 and before.json().get("exists") is True

    delete_res = requests.delete(
        f"{API}/schedule",
        params={"yil": throwaway_yil, "ay": throwaway_ay},
        headers=admin_headers,
        timeout=30,
    )
    assert delete_res.status_code == 200, delete_res.text
    assert delete_res.json().get("success") is True

    # idempotent davranış
    delete_res_2 = requests.delete(
        f"{API}/schedule",
        params={"yil": throwaway_yil, "ay": throwaway_ay},
        headers=admin_headers,
        timeout=30,
    )
    assert delete_res_2.status_code == 200 and delete_res_2.json().get("success") is True

    after = requests.get(
        f"{API}/schedule/{throwaway_yil}/{throwaway_ay}",
        headers=admin_headers,
        timeout=30,
    )
    assert after.status_code == 200 and after.json().get("exists") is False

    october = requests.get(f"{API}/schedule/2026/10", headers=admin_headers, timeout=30)
    assert october.status_code == 200
    assert october.json().get("exists") is True, "Ekim 2026 listesi silinmemeli"
