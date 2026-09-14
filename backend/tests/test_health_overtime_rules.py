"""Sağlıkçı/sağlıkçı+sürücü zorunlu mesai ve fazla mesai dağıtım kuralları testleri."""
from __future__ import annotations

import random
import sys
from pathlib import Path
from datetime import date

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scheduler import generate_schedule, SchedulerContext


def _mk_person(pid: str, ad: str, tur: str, hedef: int, fazla: bool = True, **extra):
    base = {
        "id": pid,
        "ad_soyad": ad,
        "personel_turu": tur,
        "aktif": True,
        "hedef_saat": hedef,
        "fazla_mesai": fazla,
        "surucu_tercihi": "yok",
    }
    base.update(extra)
    return base


def _overtime_shift_counts(schedule, personnel, targets):
    # Kişi bazında "zorunlu saat üzeri kalan" nöbet adedi
    order = {g.tarih: i for i, g in enumerate(schedule.gunler)}
    assignments = sorted(
        schedule.assignments,
        key=lambda a: (order.get(a.tarih, 10_000), a.tarih, a.gorev, a.personel_id),
    )
    hours = {p["id"]: 0 for p in personnel}
    overtime = {p["id"]: 0 for p in personnel}
    for a in assignments:
        pid = a.personel_id
        prev = hours[pid]
        new = prev + int(a.saat)
        if new > int(targets.get(pid, 0)):
            overtime[pid] += 1
        hours[pid] = new
    return overtime, hours


def _base_personnel(hedef=288):
    sag = [
        _mk_person("s1", "Sağlıkçı 1", "saglikci", hedef, True),
        _mk_person("s2", "Sağlıkçı 2", "saglikci", hedef, True),
        _mk_person("ss1", "Sağlıkçı+Sürücü 1", "saglikci_surucu", hedef, True),
        _mk_person("ss2", "Sağlıkçı+Sürücü 2", "saglikci_surucu", hedef, True),
    ]
    drv = [
        _mk_person("d1", "Sürücü 1", "surucu", 180, True),
        _mk_person("d2", "Sürücü 2", "surucu", 180, True),
        _mk_person("d3", "Sürücü 3", "surucu", 180, True),
        _mk_person("d4", "Sürücü 4", "surucu", 180, True),
    ]
    return sag + drv


def test_mandatory_hours_prioritized_and_reached_when_feasible():
    random.seed(42)
    personnel = _base_personnel(hedef=288)
    leaves = {}
    targets = {p["id"]: (288 if p["personel_turu"] in ("saglikci", "saglikci_surucu") else 180) for p in personnel}

    schedule, errors = generate_schedule(
        2027,
        3,
        personnel,
        leaves,
        max_gun_asiri=3,
        holidays=set(),
        carryover_days=[],
        targets=targets,
    )

    assert schedule.gunler, "Program oluşturulmalı"
    sag_ids = [p["id"] for p in personnel if p["personel_turu"] in ("saglikci", "saglikci_surucu")]
    _ot, hours = _overtime_shift_counts(schedule, personnel, targets)

    for pid in sag_ids:
        assert hours[pid] >= targets[pid], f"{pid} zorunlu saatini dolduramadı: {hours[pid]}/{targets[pid]}"

    assert not any("zorunlu mesai saati tamamlanamadı" in e for e in errors), errors


def test_overtime_equal_distribution_for_overtime_wanting_health_staff():
    random.seed(7)
    personnel = _base_personnel(hedef=288)
    leaves = {}
    targets = {p["id"]: (288 if p["personel_turu"] in ("saglikci", "saglikci_surucu") else 180) for p in personnel}

    schedule, _errors = generate_schedule(
        2027,
        3,
        personnel,
        leaves,
        max_gun_asiri=3,
        holidays=set(),
        carryover_days=[],
        targets=targets,
    )

    wanting = [p["id"] for p in personnel if p["personel_turu"] in ("saglikci", "saglikci_surucu") and p.get("fazla_mesai")]
    overtime, _hours = _overtime_shift_counts(schedule, personnel, targets)
    values = [overtime[pid] for pid in wanting]

    assert sum(values) > 0, "Fazla mesai oluşmalı"
    assert max(values) - min(values) <= 1, f"Fazla mesai adaleti bozuk: {dict((pid, overtime[pid]) for pid in wanting)}"


def test_non_overtime_wanting_gets_overtime_only_last_resort_when_wanting_blocked():
    random.seed(11)
    personnel = _base_personnel(hedef=72)

    # Sağlıkçılar arasında iki kişi fazla mesai ister, diğer ikisi istemez.
    for p in personnel:
        if p["id"] in ("s1", "s2"):
            p["fazla_mesai"] = True
        if p["id"] in ("ss1", "ss2"):
            p["fazla_mesai"] = False

    # İsteyenleri ayın ikinci yarısında bloklayarak son çare senaryosu oluştur.
    leaves = {
        "s1": {f"2027-03-{d:02d}": "yillik_izin" for d in range(16, 29)},
        "s2": {f"2027-03-{d:02d}": "yillik_izin" for d in range(16, 29)},
    }
    targets = {p["id"]: (72 if p["personel_turu"] in ("saglikci", "saglikci_surucu") else 180) for p in personnel}

    schedule, _errors = generate_schedule(
        2027,
        3,
        personnel,
        leaves,
        max_gun_asiri=3,
        holidays=set(),
        carryover_days=[],
        targets=targets,
    )

    ctx = SchedulerContext(personnel, leaves, holidays=set(), targets=targets)
    wanting = [p["id"] for p in personnel if p["personel_turu"] in ("saglikci", "saglikci_surucu") and p.get("fazla_mesai")]
    non_wanting = [p["id"] for p in personnel if p["personel_turu"] in ("saglikci", "saglikci_surucu") and not p.get("fazla_mesai")]

    day_map = {g.tarih: g for g in schedule.gunler}
    seen_last_resort_case = False

    for tarih in sorted(day_map.keys()):
        d = date.fromisoformat(tarih)
        day = day_map[tarih]
        for slot in ("saglikci_1", "saglikci_2"):
            pid = getattr(day, slot)
            if not pid:
                continue

            is_non_wanting_overtime = (
                pid in non_wanting and ctx.assignment_creates_overtime(pid, "saglikci_24")
            )
            if is_non_wanting_overtime:
                wanting_suitable = [wid for wid in wanting if ctx.can_assign(wid, d, "saglikci_24")[0]]
                assert not wanting_suitable, (
                    f"{tarih}/{slot} için isteyen uygun aday varken istemeyene fazla mesai yazıldı: {wanting_suitable}"
                )
                seen_last_resort_case = True

            ctx.assign(pid, d, "saglikci_24")

    assert seen_last_resort_case, "Son çare fazla mesai senaryosu oluşmadı"
