from typing import List, Literal
from datetime import date
from calendar import monthrange
import random

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, current_station
from models import (
    GenerateRequest, ManualUpdateRequest, CarryoverSet,
    TemplateCreate, Template, TemplateApply, LeaveRequest,
)
from scheduler import generate_schedule, validate_manual_assignment, compute_violations, TASKS
from helpers import (
    get_active_personnel_list, build_leaves_map, get_holidays, build_targets,
    get_carryover, find_conflicts, personnel_card_data, card_text, now_iso_helper,
)

router = APIRouter(prefix="/api", tags=["schedules"])


@router.get("/schedule/{yil}/{ay}")
async def get_schedule(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    doc = await db.schedules.find_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc:
        return {"exists": False, "yil": yil, "ay": ay}
    return {"exists": True, **doc}


@router.post("/schedule/generate")
async def do_generate(req: GenerateRequest, istasyon_id: str = Depends(current_station)):
    personnel = await get_active_personnel_list(istasyon_id)
    active = [p for p in personnel if p.get("aktif", True)]
    if len(active) < 3:
        raise HTTPException(400, "En az 3 aktif personel gerekli")
    pmap = {p["id"]: p for p in personnel}
    holidays = {h["tarih"] for h in await get_holidays(req.yil)}
    carry = await get_carryover(req.yil, req.ay, istasyon_id)
    ignored = list(req.ignore_leave_ids)

    attempts = 0
    while True:
        leaves = await build_leaves_map(istasyon_id, ignored)
        tinfo = await build_targets(req.yil, req.ay, active, leaves)
        targets = {k: t["normal_hedef"] for k, t in tinfo.items()}
        schedule, errors = generate_schedule(req.yil, req.ay, active, leaves, req.max_gun_asiri,
                                             holidays, carry["gunler"], targets)
        conflicts = await find_conflicts(errors, ignored, pmap, istasyon_id)
        if not errors or not req.rastgele_yoksay or attempts >= 10:
            break
        pool = [c for c in conflicts if c["durum"] == "nobet_istemiyor"] or conflicts
        if not pool:
            break
        ignored.append(random.choice(pool)["id"])
        attempts += 1

    doc = schedule.model_dump()
    doc["istasyon_id"] = istasyon_id
    doc["updated_at"] = now_iso_helper()
    doc["yoksayilan_istekler"] = ignored
    doc["gecis_kaynagi"] = carry["kaynak"]
    await db.schedules.update_one(
        {"yil": req.yil, "ay": req.ay, "istasyon_id": istasyon_id},
        {"$set": doc}, upsert=True,
    )
    ipucu = None
    if errors and not any(p.get("fazla_mesai") for p in active):
        ipucu = ("Hiçbir personel fazla mesai için seçili değil. Normal çalışma saatleri dolduğunda kalan görevler "
                 "atanamaz; Personeller sayfasından fazla mesai yapabilecek personelleri seçin.")
    return {"success": len(errors) == 0, "errors": errors, "schedule": doc,
            "conflicts": conflicts, "ignored": ignored, "carryover": carry, "ipucu": ipucu}


@router.post("/schedule/manual")
async def manual_update(req: ManualUpdateRequest, istasyon_id: str = Depends(current_station)):
    doc = await db.schedules.find_one({"yil": req.yil, "ay": req.ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Nöbet listesi bulunamadı")

    personnel = await get_active_personnel_list(istasyon_id)
    leaves = await build_leaves_map(istasyon_id, doc.get("yoksayilan_istekler"))
    carry = await get_carryover(req.yil, req.ay, istasyon_id)

    if req.personel_id:
        if not any(p["id"] == req.personel_id for p in personnel):
            raise HTTPException(404, "Personel bulunamadı")
        tinfo = await build_targets(req.yil, req.ay, personnel, leaves)
        targets = {k: t["normal_hedef"] for k, t in tinfo.items()}
        ok, msg = validate_manual_assignment(doc, req.tarih, req.slot, req.personel_id, personnel,
                                             leaves, carry["gunler"], targets)
        if not ok:
            return {"success": False, "message": f"Kural ihlali: {msg}"}

    updated = False
    slot_to_task = {
        "saglikci_1": "saglikci_24", "saglikci_2": "saglikci_24",
        "surucu_gunduz": "surucu_gunduz", "surucu_gece": "surucu_gece", "surucu_24": "surucu_24",
    }
    for day in doc["gunler"]:
        if day["tarih"] == req.tarih:
            day[req.slot] = req.personel_id
            task = slot_to_task[req.slot]
            new_assignments = []
            removed_once = False
            for a in doc.get("assignments", []):
                if (a["tarih"] == req.tarih and a["gorev"] == task and not removed_once):
                    removed_once = True
                    continue
                new_assignments.append(a)
            doc["assignments"] = new_assignments
            if req.personel_id:
                t = TASKS[task]
                doc["assignments"].append({
                    "tarih": req.tarih, "personel_id": req.personel_id, "gorev": task,
                    "baslangic": t["start"], "bitis": t["end"], "saat": t["hours"],
                })
            updated = True
            break

    if not updated:
        raise HTTPException(404, "Gün bulunamadı")

    doc["updated_at"] = now_iso_helper()
    await db.schedules.update_one({"yil": req.yil, "ay": req.ay, "istasyon_id": istasyon_id}, {"$set": doc})
    return {"success": True, "schedule": doc}


@router.get("/schedule/{yil}/{ay}/violations")
async def get_violations(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    doc = await db.schedules.find_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc:
        return {"violations": []}
    personnel = await get_active_personnel_list(istasyon_id)
    leaves = await build_leaves_map(istasyon_id, doc.get("yoksayilan_istekler"))
    carry = await get_carryover(yil, ay, istasyon_id)
    tinfo = await build_targets(yil, ay, personnel, leaves)
    targets = {k: t["normal_hedef"] for k, t in tinfo.items()}
    return {"violations": compute_violations(doc, personnel, leaves, carry["gunler"], targets)}


@router.get("/schedule/{yil}/{ay}/personnel/{pid}/card")
async def personnel_card(yil: int, ay: int, pid: str, istasyon_id: str = Depends(current_station)):
    p, items, toplam = await personnel_card_data(yil, ay, pid, istasyon_id)
    return {"personel": p, "nobetler": items, "toplam_saat": toplam, "toplam_nobet": len(items),
            "mesaj": card_text(p, yil, ay, items, toplam)}


class CandidatesRequest(BaseModel):
    yil: int
    ay: int
    tarih: str
    slot: Literal["saglikci_1", "saglikci_2", "surucu_gunduz", "surucu_gece", "surucu_24"]


@router.post("/schedule/candidates")
async def slot_candidates(req: CandidatesRequest, istasyon_id: str = Depends(current_station)):
    doc = await db.schedules.find_one({"yil": req.yil, "ay": req.ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Nöbet listesi bulunamadı")
    personnel = await get_active_personnel_list(istasyon_id)
    leaves = await build_leaves_map(istasyon_id, doc.get("yoksayilan_istekler"))
    carry = await get_carryover(req.yil, req.ay, istasyon_id)
    hours = {}
    for a in doc.get("assignments", []):
        hours[a["personel_id"]] = hours.get(a["personel_id"], 0) + a["saat"]
    current = next((g.get(req.slot) for g in doc["gunler"] if g["tarih"] == req.tarih), None)
    tinfo = await build_targets(req.yil, req.ay, personnel, leaves)
    targets = {k: t["normal_hedef"] for k, t in tinfo.items()}
    roles = {"saglikci_1": ("saglikci", "saglikci_surucu"), "saglikci_2": ("saglikci", "saglikci_surucu"),
             "surucu_gunduz": ("surucu", "saglikci_surucu"), "surucu_gece": ("surucu", "saglikci_surucu"),
             "surucu_24": ("saglikci_surucu",)}[req.slot]
    out = []
    for p in personnel:
        if not p.get("aktif", True) or p["personel_turu"] not in roles:
            continue
        ok, msg = validate_manual_assignment(doc, req.tarih, req.slot, p["id"], personnel,
                                             leaves, carry["gunler"], targets)
        out.append({
            "personel_id": p["id"], "ad_soyad": p["ad_soyad"], "personel_turu": p["personel_turu"],
            "uygun": ok, "mesaj": msg, "mevcut": p["id"] == current,
            "tercih_uyarisi": leaves.get(p["id"], {}).get(req.tarih) == "nobet_istemiyor",
            "saat": hours.get(p["id"], 0), "hedef_saat": targets.get(p["id"], p.get("hedef_saat", 180)),
            "fazla_mesai": p.get("fazla_mesai", False),
        })
    out.sort(key=lambda c: (not c["uygun"], c["tercih_uyarisi"], c["saat"]))
    rank = 0
    for c in out:
        if c["uygun"] and not c["tercih_uyarisi"] and not c["mevcut"] and rank < 3:
            c["onerilen"] = True
            rank += 1
        else:
            c["onerilen"] = False
    return {"adaylar": out}


@router.get("/schedule/{yil}/{ay}/summary")
async def schedule_summary(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    doc = await db.schedules.find_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc:
        return {"exists": False}
    personnel = await get_active_personnel_list(istasyon_id)
    leaves = await build_leaves_map(istasyon_id, doc.get("yoksayilan_istekler"))
    carry = await get_carryover(yil, ay, istasyon_id)
    tinfo = await build_targets(yil, ay, personnel, leaves)
    viol = compute_violations(doc, personnel, leaves, carry["gunler"], {k: t["normal_hedef"] for k, t in tinfo.items()})
    empty = []
    for g in doc["gunler"]:
        if not g.get("saglikci_1"):
            empty.append({"tarih": g["tarih"], "slot": "saglikci_1", "label": "Sağlıkçı 1"})
        if not g.get("saglikci_2"):
            empty.append({"tarih": g["tarih"], "slot": "saglikci_2", "label": "Sağlıkçı 2"})
        if not g.get("surucu_24"):
            if not g.get("surucu_gunduz"):
                empty.append({"tarih": g["tarih"], "slot": "surucu_gunduz", "label": "Sürücü 09-21"})
            if not g.get("surucu_gece"):
                empty.append({"tarih": g["tarih"], "slot": "surucu_gece", "label": "Sürücü 21-09"})
    return {
        "exists": True, "gun_sayisi": len(doc["gunler"]),
        "hard": [v for v in viol if v["tur"] == "hard"],
        "soft": [v for v in viol if v["tur"] == "soft"],
        "bos_gorevler": empty,
        "yoksayilan_istek_sayisi": len(doc.get("yoksayilan_istekler", [])),
        "updated_at": doc.get("updated_at"),
    }


@router.get("/schedule/{yil}/{ay}/stats")
async def get_stats(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    doc = await db.schedules.find_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Liste yok")
    personnel = await get_active_personnel_list(istasyon_id)
    pmap = {p["id"]: p for p in personnel}
    holidays = {h["tarih"] for h in await get_holidays(yil)}
    leaves = await build_leaves_map(istasyon_id)
    tinfo = await build_targets(yil, ay, personnel, leaves)

    stats = {}
    for pid, p in pmap.items():
        t = tinfo[pid]
        stats[pid] = {
            "personel_id": pid, "ad_soyad": p["ad_soyad"], "personel_turu": p["personel_turu"],
            "hedef_saat": t["normal_hedef"], "normal_hedef": t["normal_hedef"],
            "hafta_ici_gun": t["hafta_ici_gun"], "tatil_gun": t["tatil_gun"], "izin_gun": t["izin_gun"],
            "fazla_mesai_secili": p.get("fazla_mesai", False),
            "nobet_1_15": 0, "nobet_16_son": 0,
            "nobet_hedef_1_15": p.get("nobet_hedef_1_15") if p["personel_turu"] == "surucu" else None,
            "nobet_hedef_16_son": p.get("nobet_hedef_16_son") if p["personel_turu"] == "surucu" else None,
            "toplam_saat": 0, "toplam_nobet": 0, "cumartesi": 0, "pazar": 0, "hafta_sonu": 0,
            "tatil": 0, "gunduz": 0, "gece": 0, "surucu_24": 0, "saglikci_24": 0,
        }
    for a in doc.get("assignments", []):
        pid = a["personel_id"]
        if pid not in stats:
            continue
        s = stats[pid]
        s["toplam_saat"] += a["saat"]
        s["toplam_nobet"] += 1
        d = date.fromisoformat(a["tarih"])
        if d.day <= 15:
            s["nobet_1_15"] += 1
        else:
            s["nobet_16_son"] += 1
        if a["tarih"] in holidays:
            s["tatil"] += 1
        if d.weekday() == 5:
            s["cumartesi"] += 1
            s["hafta_sonu"] += 1
        elif d.weekday() == 6:
            s["pazar"] += 1
            s["hafta_sonu"] += 1
        if a["gorev"] == "surucu_gunduz":
            s["gunduz"] += 1
        elif a["gorev"] == "surucu_gece":
            s["gece"] += 1
        elif a["gorev"] == "surucu_24":
            s["surucu_24"] += 1
        elif a["gorev"] == "saglikci_24":
            s["saglikci_24"] += 1

    for s in stats.values():
        s["fark"] = s["toplam_saat"] - s["hedef_saat"]
        s["gerceklesen"] = s["toplam_saat"]
        s["eksik_saat"] = max(0, s["normal_hedef"] - s["toplam_saat"])
        s["fazla_mesai"] = max(0, s["toplam_saat"] - s["normal_hedef"])

    return {"yil": yil, "ay": ay, "stats": list(stats.values())}


@router.get("/schedule/{yil}/{ay}/targets")
async def get_targets(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    personnel = await get_active_personnel_list(istasyon_id)
    leaves = await build_leaves_map(istasyon_id)
    tinfo = await build_targets(yil, ay, personnel, leaves)
    return {"yil": yil, "ay": ay, "targets": [
        {"personel_id": p["id"], "ad_soyad": p["ad_soyad"], **tinfo[p["id"]]} for p in personnel]}


# ------------- carryover -------------
@router.get("/carryover/{yil}/{ay}")
async def carryover_get(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    return await get_carryover(yil, ay, istasyon_id)


@router.put("/carryover/{yil}/{ay}")
async def carryover_set(yil: int, ay: int, data: CarryoverSet, istasyon_id: str = Depends(current_station)):
    gunler = [g.model_dump() for g in data.gunler
              if g.saglikci_1 or g.saglikci_2 or g.surucu_gunduz or g.surucu_gece or g.surucu_24]
    await db.carryover.update_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id},
                                  {"$set": {"yil": yil, "ay": ay, "istasyon_id": istasyon_id,
                                            "gunler": gunler, "updated_at": now_iso_helper()}},
                                  upsert=True)
    return await get_carryover(yil, ay, istasyon_id)


# ------------- templates -------------
@router.get("/templates", response_model=List[Template])
async def list_templates(istasyon_id: str = Depends(current_station)):
    return await db.templates.find({"istasyon_id": istasyon_id}, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.post("/templates", response_model=Template)
async def create_template(data: TemplateCreate, istasyon_id: str = Depends(current_station)):
    personnel = await get_active_personnel_list(istasyon_id)
    personel = [{"personel_id": p["id"], "ad_soyad": p["ad_soyad"], "aktif": p.get("aktif", True),
                 "hedef_saat": p.get("hedef_saat", 180)} for p in personnel]
    tercihler = []
    if data.kaynak_yil and data.kaynak_ay:
        prefix = f"{data.kaynak_yil:04d}-{data.kaynak_ay:02d}"
        docs = await db.leaves.find({"istasyon_id": istasyon_id, "durum": "nobet_istemiyor",
                                     "tarih": {"$regex": f"^{prefix}"}}, {"_id": 0}).to_list(10000)
        counter = {}
        for d in docs:
            key = (d["personel_id"], date.fromisoformat(d["tarih"]).weekday())
            counter[key] = counter.get(key, 0) + 1
        tercihler = [{"personel_id": k[0], "haftanin_gunu": k[1]} for k, v in counter.items() if v >= 2]
    obj = Template(ad=data.ad, aciklama=data.aciklama, personel=personel, tercihler=tercihler)
    doc = obj.model_dump()
    doc["istasyon_id"] = istasyon_id
    await db.templates.insert_one(doc)
    return obj


@router.delete("/templates/{tid}")
async def delete_template(tid: str, istasyon_id: str = Depends(current_station)):
    res = await db.templates.delete_one({"id": tid, "istasyon_id": istasyon_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Şablon bulunamadı")
    return {"deleted": True}


@router.post("/templates/{tid}/apply")
async def apply_template(tid: str, data: TemplateApply, istasyon_id: str = Depends(current_station)):
    tpl = await db.templates.find_one({"id": tid, "istasyon_id": istasyon_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(404, "Şablon bulunamadı")
    updated = 0
    for tp in tpl.get("personel", []):
        res = await db.personnel.update_one({"id": tp["personel_id"], "istasyon_id": istasyon_id},
                                            {"$set": {"aktif": tp["aktif"], "hedef_saat": tp["hedef_saat"]}})
        updated += res.matched_count
    _, dim = monthrange(data.yil, data.ay)
    added = 0
    for pref in tpl.get("tercihler", []):
        for dnum in range(1, dim + 1):
            d = date(data.yil, data.ay, dnum)
            if d.weekday() != pref["haftanin_gunu"]:
                continue
            exists = await db.leaves.find_one({"personel_id": pref["personel_id"], "tarih": d.isoformat()})
            if exists:
                continue
            await db.leaves.insert_one(LeaveRequest(istasyon_id=istasyon_id, personel_id=pref["personel_id"],
                                                    tarih=d.isoformat(), durum="nobet_istemiyor").model_dump())
            added += 1
    return {"success": True, "personel_guncellendi": updated, "tercih_eklendi": added}
