"""Shared scheduling/data helpers used across routers."""
from __future__ import annotations
from datetime import date, timedelta
from typing import List, Optional

from fastapi import HTTPException

from deps import db
from holidays import official_holidays
from scheduler import compute_normal_target
from models import now_iso as now_iso_helper

GUNLER_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cts", "Paz"]
MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


async def get_active_personnel_list(istasyon_id: str) -> List[dict]:
    return await db.personnel.find({"istasyon_id": istasyon_id}, {"_id": 0}).to_list(1000)


async def build_leaves_map(istasyon_id: str, ignore_ids: Optional[List[str]] = None) -> dict:
    ignore = set(ignore_ids or [])
    leaves: dict = {}
    async for d in db.leaves.find({"istasyon_id": istasyon_id}, {"_id": 0}):
        if d.get("id") in ignore:
            continue
        pid = d["personel_id"]
        leaves.setdefault(pid, {})[d["tarih"]] = d["durum"]
    return leaves


async def get_holidays(yil: int) -> List[dict]:
    out = official_holidays(yil)
    custom = await db.holidays.find({"tarih": {"$regex": f"^{yil:04d}"}}, {"_id": 0}).to_list(1000)
    out += [{"tarih": c["tarih"], "ad": c["ad"], "kaynak": "ozel", "id": c["id"]} for c in custom]
    return sorted(out, key=lambda h: h["tarih"])


async def build_targets(yil: int, ay: int, personnel: List[dict], leaves: dict) -> dict:
    holidays = {h["tarih"] for h in await get_holidays(yil)}
    return {p["id"]: compute_normal_target(yil, ay, p["id"], leaves, holidays) for p in personnel}


def prev_month(yil: int, ay: int):
    return (yil - 1, 12) if ay == 1 else (yil, ay - 1)


async def get_carryover(yil: int, ay: int, istasyon_id: str) -> dict:
    py, pm = prev_month(yil, ay)
    prev = await db.schedules.find_one({"yil": py, "ay": pm, "istasyon_id": istasyon_id}, {"_id": 0})
    if prev and prev.get("gunler"):
        return {"kaynak": "onceki_liste", "gunler": prev["gunler"][-3:], "onceki_yil": py, "onceki_ay": pm}
    manual = await db.carryover.find_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if manual and manual.get("gunler"):
        return {"kaynak": "manuel", "gunler": manual["gunler"], "onceki_yil": py, "onceki_ay": pm}
    return {"kaynak": "yok", "gunler": [], "onceki_yil": py, "onceki_ay": pm}


def _conflict_dates(errors: List[str]) -> set:
    out = set()
    for e in errors:
        try:
            d = date.fromisoformat(e[:10])
        except ValueError:
            continue
        for off in (-1, 0, 1):
            out.add((d + timedelta(days=off)).isoformat())
    return out


async def find_conflicts(errors: List[str], ignored: List[str], pmap: dict, istasyon_id: str) -> List[dict]:
    dates = _conflict_dates(errors)
    if not dates:
        return []
    docs = await db.leaves.find({"istasyon_id": istasyon_id, "tarih": {"$in": sorted(dates)}}, {"_id": 0}).to_list(1000)
    out = []
    for d in docs:
        if d["id"] in ignored or d["personel_id"] not in pmap:
            continue
        out.append({**d, "ad_soyad": pmap[d["personel_id"]]["ad_soyad"]})
    out.sort(key=lambda x: (x["tarih"], x["durum"] != "nobet_istemiyor"))
    return out


def fmt_task_label(task: str) -> str:
    return {
        "saglikci_24": "Sağlıkçı 24s",
        "surucu_gunduz": "Sürücü 09-21",
        "surucu_gece": "Sürücü 21-09",
        "surucu_24": "Sürücü 24s",
    }.get(task, task)


async def personnel_card_data(yil: int, ay: int, pid: str, istasyon_id: str):
    doc = await db.schedules.find_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Liste yok")
    p = await db.personnel.find_one({"id": pid, "istasyon_id": istasyon_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Personel bulunamadı")
    holidays = {h["tarih"]: h["ad"] for h in await get_holidays(yil)}
    items = []
    for a in sorted(doc.get("assignments", []), key=lambda x: x["tarih"]):
        if a["personel_id"] != pid:
            continue
        d = date.fromisoformat(a["tarih"])
        items.append({
            "tarih": a["tarih"], "gun": GUNLER_TR[d.weekday()], "gorev": fmt_task_label(a["gorev"]),
            "saat_araligi": f"{a['baslangic']}-{a['bitis']}", "saat": a["saat"],
            "tatil": holidays.get(a["tarih"]), "hafta_sonu": d.weekday() >= 5,
        })
    toplam = sum(i["saat"] for i in items)
    return p, items, toplam


def card_text(p: dict, yil: int, ay: int, items: List[dict], toplam: int) -> str:
    lines = [f"🚑 112 Nöbet Listesi — {MONTHS_TR[ay - 1]} {yil}", f"👤 {p['ad_soyad']}", ""]
    for i in items:
        d = date.fromisoformat(i["tarih"])
        extra = f" 🏖 {i['tatil']}" if i["tatil"] else ""
        lines.append(f"• {d.day:02d} {MONTHS_TR[ay - 1][:3]} {i['gun']} — {i['gorev']} ({i['saat_araligi']}){extra}")
    lines += ["", f"Toplam: {len(items)} nöbet / {toplam} saat"]
    return "\n".join(lines)
