from scheduler import generate_schedule


def _person(pid, role):
    return {
        "id": pid,
        "ad_soyad": pid,
        "personel_turu": role,
        "aktif": True,
        "hedef_saat": 0,
        "fazla_mesai": False,
        "surucu_tercihi": "yok",
        "nobet_hedef_1_15": None,
        "nobet_hedef_16_son": None,
    }


def test_each_day_has_paramedic_att_and_driver_only_from_driver_role():
    personnel = (
        [_person(f"p{i}", "paramedik") for i in range(1, 9)]
        + [_person(f"a{i}", "att") for i in range(1, 9)]
        + [_person(f"d{i}", "surucu") for i in range(1, 13)]
    )
    schedule, _errors = generate_schedule(
        2026, 2, personnel, leaves={}, targets={p["id"]: 0 for p in personnel}
    )
    roles = {p["id"]: p["personel_turu"] for p in personnel}

    assert len(schedule.gunler) == 28
    for day in schedule.gunler:
        assert day.saglikci_1 is not None
        assert day.saglikci_2 is not None
        assert roles[day.saglikci_1] == "paramedik"
        assert roles[day.saglikci_2] == "att"
        driver_ids = [day.surucu_24] if day.surucu_24 else [day.surucu_gunduz, day.surucu_gece]
        assert all(pid is not None and roles[pid] == "surucu" for pid in driver_ids)
