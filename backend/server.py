from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import logging
from pathlib import Path
from typing import List, Optional, Literal
from pydantic import BaseModel
from calendar import monthrange
from datetime import date, timedelta
import random

from models import (
    Personnel, PersonnelCreate, PersonnelUpdate,
    LeaveRequest, LeaveBulkSet,
    MonthlySchedule, GenerateRequest, ManualUpdateRequest,
    HolidayCreate, Holiday, CarryoverSet, TemplateCreate, Template, TemplateApply,
    Station, StationCreate, User, UserCreate, UserUpdate, LoginRequest,
    ChangePasswordRequest, AssignOrphansRequest,
    new_id, now_iso,
)
from scheduler import generate_schedule, validate_manual_assignment, compute_violations, compute_normal_target, TASKS
from seed import DEMO_PERSONNEL
from holidays import official_holidays
from auth import hash_password, verify_password, create_token, decode_token

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="112 Nöbet Listesi API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ------------- auth dependencies -------------
async def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Giriş gerekli")
    payload = decode_token(auth_header[7:])
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "Kullanıcı bulunamadı")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Bu işlem için yetkiniz yok")
    return user


async def current_station(request: Request, user: dict = Depends(get_current_user)) -> str:
    """Resolve the station the request operates on and enforce isolation."""
    if user.get("role") == "istasyon_sorumlusu":
        if not user.get("istasyon_id"):
            raise HTTPException(403, "Hesabınıza bir istasyon atanmamış")
        return user["istasyon_id"]
    # admin: station chosen via header
    sid = request.headers.get("X-Istasyon-Id")
    if not sid:
        raise HTTPException(400, "Lütfen üst menüden bir istasyon seçin")
    st = await db.stations.find_one({"id": sid})
    if not st:
        raise HTTPException(404, "İstasyon bulunamadı")
    return sid


# ------------- helpers -------------
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


# ------------- root -------------
@api_router.get("/")
async def root():
    return {"message": "112 Nöbet Listesi API", "ok": True}


@api_router.get("/health")
async def health():
    return {"status": "ok"}


# ------------- auth -------------
@api_router.post("/auth/login")
async def login(data: LoginRequest):
    user = await db.users.find_one({"kullanici_adi": data.kullanici_adi})
    if not user or not verify_password(data.sifre, user.get("password_hash", "")):
        raise HTTPException(401, "Kullanıcı adı veya şifre hatalı")
    token = create_token(user["id"])
    user.pop("_id", None)
    user.pop("password_hash", None)
    if user.get("istasyon_id"):
        st = await db.stations.find_one({"id": user["istasyon_id"]}, {"_id": 0})
        user["istasyon_ad"] = st["ad"] if st else None
    return {"token": token, "user": user}


@api_router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    if user.get("istasyon_id"):
        st = await db.stations.find_one({"id": user["istasyon_id"]}, {"_id": 0})
        user["istasyon_ad"] = st["ad"] if st else None
    return user


@api_router.post("/auth/change-password")
async def change_password(data: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    full = await db.users.find_one({"id": user["id"]})
    if not full or not verify_password(data.eski_sifre, full.get("password_hash", "")):
        raise HTTPException(400, "Mevcut şifre hatalı")
    if len(data.yeni_sifre) < 4:
        raise HTTPException(400, "Yeni şifre en az 4 karakter olmalı")
    await db.users.update_one({"id": user["id"]},
                              {"$set": {"password_hash": hash_password(data.yeni_sifre), "sifre_degistirildi": True}})
    return {"success": True}


# ------------- stations (admin) -------------
@api_router.get("/stations")
async def list_stations(user: dict = Depends(require_admin)):
    stations = await db.stations.find({}, {"_id": 0}).sort("ad", 1).to_list(1000)
    for s in stations:
        s["personel_sayisi"] = await db.personnel.count_documents({"istasyon_id": s["id"]})
    return stations


@api_router.post("/stations", response_model=Station)
async def create_station(data: StationCreate, user: dict = Depends(require_admin)):
    obj = Station(ad=data.ad)
    await db.stations.insert_one(obj.model_dump())
    return obj


@api_router.patch("/stations/{sid}")
async def update_station(sid: str, data: StationCreate, user: dict = Depends(require_admin)):
    res = await db.stations.update_one({"id": sid}, {"$set": {"ad": data.ad}})
    if res.matched_count == 0:
        raise HTTPException(404, "İstasyon bulunamadı")
    return await db.stations.find_one({"id": sid}, {"_id": 0})


@api_router.delete("/stations/{sid}")
async def delete_station(sid: str, user: dict = Depends(require_admin)):
    if await db.personnel.count_documents({"istasyon_id": sid}) or await db.users.count_documents({"istasyon_id": sid}):
        raise HTTPException(400, "İstasyona bağlı personel veya kullanıcı var; önce onları silin/taşıyın")
    res = await db.stations.delete_one({"id": sid})
    if res.deleted_count == 0:
        raise HTTPException(404, "İstasyon bulunamadı")
    return {"deleted": True}


# ------------- users / station managers (admin) -------------
@api_router.get("/users")
async def list_users(user: dict = Depends(require_admin)):
    users = await db.users.find({"role": "istasyon_sorumlusu"}, {"_id": 0, "password_hash": 0}).to_list(1000)
    stations = {s["id"]: s["ad"] for s in await db.stations.find({}, {"_id": 0}).to_list(1000)}
    for u in users:
        u["istasyon_ad"] = stations.get(u.get("istasyon_id"))
    return users


@api_router.post("/users")
async def create_user(data: UserCreate, user: dict = Depends(require_admin)):
    if await db.users.find_one({"kullanici_adi": data.kullanici_adi}):
        raise HTTPException(400, "Bu kullanıcı adı zaten kullanılıyor")
    st = await db.stations.find_one({"id": data.istasyon_id})
    if not st:
        raise HTTPException(404, "İstasyon bulunamadı")
    obj = User(kullanici_adi=data.kullanici_adi, role="istasyon_sorumlusu", istasyon_id=data.istasyon_id)
    doc = obj.model_dump()
    doc["password_hash"] = hash_password(data.sifre)
    await db.users.insert_one(doc)
    return {**obj.model_dump(), "istasyon_ad": st["ad"]}


@api_router.patch("/users/{uid}")
async def update_user(uid: str, data: UserUpdate, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"id": uid})
    if not target or target.get("role") != "istasyon_sorumlusu":
        raise HTTPException(404, "Kullanıcı bulunamadı")
    upd: dict = {}
    if data.kullanici_adi:
        other = await db.users.find_one({"kullanici_adi": data.kullanici_adi, "id": {"$ne": uid}})
        if other:
            raise HTTPException(400, "Bu kullanıcı adı zaten kullanılıyor")
        upd["kullanici_adi"] = data.kullanici_adi
    if data.istasyon_id:
        st = await db.stations.find_one({"id": data.istasyon_id})
        if not st:
            raise HTTPException(404, "İstasyon bulunamadı")
        upd["istasyon_id"] = data.istasyon_id
    if data.sifre:
        upd["password_hash"] = hash_password(data.sifre)
        upd["sifre_degistirildi"] = False
    if not upd:
        raise HTTPException(400, "Güncellenecek alan yok")
    await db.users.update_one({"id": uid}, {"$set": upd})
    return {"success": True}


@api_router.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_admin)):
    res = await db.users.delete_one({"id": uid, "role": "istasyon_sorumlusu"})
    if res.deleted_count == 0:
        raise HTTPException(404, "Kullanıcı bulunamadı")
    return {"deleted": True}


@api_router.get("/admin/orphans")
async def orphan_count(user: dict = Depends(require_admin)):
    q = {"$or": [{"istasyon_id": None}, {"istasyon_id": {"$exists": False}}]}
    return {
        "personnel": await db.personnel.count_documents(q),
        "leaves": await db.leaves.count_documents(q),
        "schedules": await db.schedules.count_documents(q),
    }


@api_router.post("/admin/assign-orphans")
async def assign_orphans(data: AssignOrphansRequest, user: dict = Depends(require_admin)):
    st = await db.stations.find_one({"id": data.istasyon_id})
    if not st:
        raise HTTPException(404, "İstasyon bulunamadı")
    q = {"$or": [{"istasyon_id": None}, {"istasyon_id": {"$exists": False}}]}
    result = {}
    for coll in ("personnel", "leaves", "schedules", "carryover", "templates"):
        r = await db[coll].update_many(q, {"$set": {"istasyon_id": data.istasyon_id}})
        result[coll] = r.modified_count
    return {"success": True, "atanan": result}


# ------------- seed -------------
@api_router.post("/seed/demo")
async def seed_demo(istasyon_id: str = Depends(current_station)):
    count = await db.personnel.count_documents({"istasyon_id": istasyon_id})
    if count > 0:
        return {"seeded": False, "existing": count}
    inserted = []
    for p in DEMO_PERSONNEL:
        obj = Personnel(istasyon_id=istasyon_id, **p)
        await db.personnel.insert_one(obj.model_dump())
        inserted.append(obj.id)
    return {"seeded": True, "count": len(inserted), "ids": inserted}


# ------------- personnel -------------
@api_router.get("/personnel", response_model=List[Personnel])
async def list_personnel(istasyon_id: str = Depends(current_station)):
    return await db.personnel.find({"istasyon_id": istasyon_id}, {"_id": 0}).to_list(1000)


@api_router.post("/personnel", response_model=Personnel)
async def create_personnel(data: PersonnelCreate, istasyon_id: str = Depends(current_station)):
    obj = Personnel(istasyon_id=istasyon_id, **data.model_dump())
    await db.personnel.insert_one(obj.model_dump())
    return obj


@api_router.patch("/personnel/{pid}", response_model=Personnel)
async def update_personnel(pid: str, data: PersonnelUpdate, istasyon_id: str = Depends(current_station)):
    update = data.model_dump(exclude_unset=True)
    if not update:
        raise HTTPException(400, "Güncellenecek alan yok")
    res = await db.personnel.update_one({"id": pid, "istasyon_id": istasyon_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Personel bulunamadı")
    return await db.personnel.find_one({"id": pid}, {"_id": 0})


@api_router.delete("/personnel/{pid}")
async def delete_personnel(pid: str, istasyon_id: str = Depends(current_station)):
    res = await db.personnel.delete_one({"id": pid, "istasyon_id": istasyon_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Personel bulunamadı")
    await db.leaves.delete_many({"personel_id": pid})
    return {"deleted": True}


# ------------- leaves / requests -------------
@api_router.get("/leaves")
async def list_leaves(istasyon_id: str = Depends(current_station),
                      personel_id: Optional[str] = None, yil: Optional[int] = None, ay: Optional[int] = None):
    q = {"istasyon_id": istasyon_id}
    if personel_id:
        q["personel_id"] = personel_id
    if yil and ay:
        prefix = f"{yil:04d}-{ay:02d}"
        q["tarih"] = {"$regex": f"^{prefix}"}
    return await db.leaves.find(q, {"_id": 0}).to_list(10000)


@api_router.post("/leaves/bulk")
async def leaves_bulk(data: LeaveBulkSet, istasyon_id: str = Depends(current_station)):
    p = await db.personnel.find_one({"id": data.personel_id, "istasyon_id": istasyon_id})
    if not p:
        raise HTTPException(404, "Personel bulunamadı")
    await db.leaves.delete_many({"personel_id": data.personel_id, "tarih": {"$in": data.tarihler}})
    if data.durum is None:
        return {"cleared": len(data.tarihler)}
    new_docs = []
    for t in data.tarihler:
        lr = LeaveRequest(istasyon_id=istasyon_id, personel_id=data.personel_id, tarih=t, durum=data.durum)
        new_docs.append(lr.model_dump())
    if new_docs:
        await db.leaves.insert_many(new_docs)
    return {"added": len(new_docs)}


# ------------- schedules -------------
@api_router.get("/schedule/{yil}/{ay}")
async def get_schedule(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    doc = await db.schedules.find_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc:
        return {"exists": False, "yil": yil, "ay": ay}
    return {"exists": True, **doc}


@api_router.post("/schedule/generate")
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
    doc["updated_at"] = now_iso()
    doc["yoksayilan_istekler"] = ignored
    doc["gecis_kaynagi"] = carry["kaynak"]
    await db.schedules.update_one(
        {"yil": req.yil, "ay": req.ay, "istasyon_id": istasyon_id},
        {"$set": doc},
        upsert=True,
    )
    ipucu = None
    if errors and not any(p.get("fazla_mesai") for p in active):
        ipucu = "Hiçbir personel fazla mesai için seçili değil. Normal çalışma saatleri dolduğunda kalan görevler atanamaz; Personeller sayfasından fazla mesai yapabilecek personelleri seçin."
    return {"success": len(errors) == 0, "errors": errors, "schedule": doc,
            "conflicts": conflicts, "ignored": ignored, "carryover": carry, "ipucu": ipucu}


@api_router.post("/schedule/manual")
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
        ok, msg = validate_manual_assignment(doc, req.tarih, req.slot, req.personel_id, personnel, leaves, carry["gunler"], targets)
        if not ok:
            return {"success": False, "message": f"Kural ihlali: {msg}"}

    updated = False
    for day in doc["gunler"]:
        if day["tarih"] == req.tarih:
            day[req.slot] = req.personel_id
            slot_to_task = {
                "saglikci_1": "saglikci_24",
                "saglikci_2": "saglikci_24",
                "surucu_gunduz": "surucu_gunduz",
                "surucu_gece": "surucu_gece",
                "surucu_24": "surucu_24",
            }
            task = slot_to_task[req.slot]
            new_assignments = []
            removed_once = False
            for a in doc.get("assignments", []):
                if (a["tarih"] == req.tarih and a["gorev"] == task and not removed_once
                        and (req.slot in ("saglikci_1", "saglikci_2")
                             or a["gorev"] == task)):
                    if req.slot in ("saglikci_1", "saglikci_2"):
                        removed_once = True
                        continue
                    removed_once = True
                    continue
                new_assignments.append(a)
            doc["assignments"] = new_assignments

            if req.personel_id:
                t = TASKS[task]
                doc["assignments"].append({
                    "tarih": req.tarih,
                    "personel_id": req.personel_id,
                    "gorev": task,
                    "baslangic": t["start"],
                    "bitis": t["end"],
                    "saat": t["hours"],
                })
            updated = True
            break

    if not updated:
        raise HTTPException(404, "Gün bulunamadı")

    doc["updated_at"] = now_iso()
    await db.schedules.update_one({"yil": req.yil, "ay": req.ay, "istasyon_id": istasyon_id}, {"$set": doc})
    return {"success": True, "schedule": doc}


# ------------- violations (canlı kural rozetleri) -------------
@api_router.get("/schedule/{yil}/{ay}/violations")
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


# ------------- personel nöbet kartı -------------
GUNLER_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cts", "Paz"]
MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


async def _personnel_card_data(yil: int, ay: int, pid: str, istasyon_id: str):
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
            "tarih": a["tarih"], "gun": GUNLER_TR[d.weekday()], "gorev": _fmt_task_label(a["gorev"]),
            "saat_araligi": f"{a['baslangic']}-{a['bitis']}", "saat": a["saat"],
            "tatil": holidays.get(a["tarih"]), "hafta_sonu": d.weekday() >= 5,
        })
    toplam = sum(i["saat"] for i in items)
    return p, items, toplam


def _card_text(p: dict, yil: int, ay: int, items: List[dict], toplam: int) -> str:
    lines = [f"🚑 112 Nöbet Listesi — {MONTHS_TR[ay - 1]} {yil}", f"👤 {p['ad_soyad']}", ""]
    for i in items:
        d = date.fromisoformat(i["tarih"])
        extra = f" 🏖 {i['tatil']}" if i["tatil"] else ""
        lines.append(f"• {d.day:02d} {MONTHS_TR[ay - 1][:3]} {i['gun']} — {i['gorev']} ({i['saat_araligi']}){extra}")
    lines += ["", f"Toplam: {len(items)} nöbet / {toplam} saat"]
    return "\n".join(lines)


@api_router.get("/schedule/{yil}/{ay}/personnel/{pid}/card")
async def personnel_card(yil: int, ay: int, pid: str, istasyon_id: str = Depends(current_station)):
    p, items, toplam = await _personnel_card_data(yil, ay, pid, istasyon_id)
    return {"personel": p, "nobetler": items, "toplam_saat": toplam, "toplam_nobet": len(items),
            "mesaj": _card_text(p, yil, ay, items, toplam)}


def _register_pdf_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    fonts_dir = ROOT_DIR / "fonts"
    try:
        if "LiberationSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("LiberationSans", str(fonts_dir / "LiberationSans-Regular.ttf")))
            pdfmetrics.registerFont(TTFont("LiberationSans-Bold", str(fonts_dir / "LiberationSans-Bold.ttf")))
        return "LiberationSans"
    except Exception:
        return "Helvetica"


def _card_elements(p: dict, yil: int, ay: int, items: List[dict], toplam: int) -> list:
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

    font = _register_pdf_font()
    bold = f"{font}-Bold" if font != "Helvetica" else "Helvetica-Bold"
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], fontName=bold)
    body = ParagraphStyle("b", parent=styles["Normal"], fontName=font, fontSize=11)
    elements = [
        Paragraph(f"112 Nöbet Kartı — {MONTHS_TR[ay - 1]} {yil}", title),
        Paragraph(f"<b>{p['ad_soyad']}</b> · {len(items)} nöbet · {toplam} saat", body),
        Spacer(1, 12),
    ]
    data = [["Tarih", "Gün", "Görev", "Saat", "Not"]]
    for i in items:
        data.append([i["tarih"], i["gun"], i["gorev"], i["saat_araligi"],
                     i["tatil"] or ("Hafta sonu" if i["hafta_sonu"] else "")])
    t = Table(data, repeatRows=1, colWidths=[80, 45, 120, 80, 180])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2A4A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), bold),
        ("FONTNAME", (0, 1), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    elements.append(t)
    return elements


def _build_pdf(elements: list) -> io.BytesIO:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36).build(elements)
    buf.seek(0)
    return buf


def _safe_name(s: str) -> str:
    from urllib.parse import quote
    return quote(s)


@api_router.get("/schedule/{yil}/{ay}/personnel/{pid}/export/pdf")
async def personnel_card_pdf(yil: int, ay: int, pid: str, istasyon_id: str = Depends(current_station)):
    p, items, toplam = await _personnel_card_data(yil, ay, pid, istasyon_id)
    buf = _build_pdf(_card_elements(p, yil, ay, items, toplam))
    fname = _safe_name(f"nobet_karti_{p['ad_soyad'].replace(' ', '_')}_{yil}_{ay:02d}.pdf")
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})


async def _all_cards(yil: int, ay: int, istasyon_id: str):
    doc = await db.schedules.find_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Liste yok")
    assigned = {a["personel_id"] for a in doc.get("assignments", [])}
    personnel = sorted([p for p in await get_active_personnel_list(istasyon_id) if p["id"] in assigned],
                       key=lambda p: p["ad_soyad"])
    out = []
    for p in personnel:
        _, items, toplam = await _personnel_card_data(yil, ay, p["id"], istasyon_id)
        out.append((p, items, toplam))
    return out


@api_router.get("/schedule/{yil}/{ay}/personnel-cards/export/pdf")
async def all_cards_pdf(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    from reportlab.platypus import PageBreak
    cards = await _all_cards(yil, ay, istasyon_id)
    elements = []
    for idx, (p, items, toplam) in enumerate(cards):
        if idx:
            elements.append(PageBreak())
        elements += _card_elements(p, yil, ay, items, toplam)
    return StreamingResponse(_build_pdf(elements), media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename=nobet_kartlari_{yil}_{ay:02d}.pdf"})


@api_router.get("/schedule/{yil}/{ay}/personnel-cards/export/zip")
async def all_cards_zip(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    import zipfile
    cards = await _all_cards(yil, ay, istasyon_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, items, toplam in cards:
            pdf = _build_pdf(_card_elements(p, yil, ay, items, toplam))
            zf.writestr(f"nobet_karti_{p['ad_soyad'].replace(' ', '_')}_{yil}_{ay:02d}.pdf", pdf.getvalue())
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename=nobet_kartlari_{yil}_{ay:02d}.zip"})


# ------------- atama ön kontrolü / takas önerisi -------------
class CandidatesRequest(BaseModel):
    yil: int
    ay: int
    tarih: str
    slot: Literal["saglikci_1", "saglikci_2", "surucu_gunduz", "surucu_gece", "surucu_24"]


@api_router.post("/schedule/candidates")
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
        ok, msg = validate_manual_assignment(doc, req.tarih, req.slot, p["id"], personnel, leaves, carry["gunler"], targets)
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


# ------------- ana sayfa özeti -------------
@api_router.get("/schedule/{yil}/{ay}/summary")
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


# ------------- statistics -------------
@api_router.get("/schedule/{yil}/{ay}/stats")
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
            "personel_id": pid,
            "ad_soyad": p["ad_soyad"],
            "personel_turu": p["personel_turu"],
            "hedef_saat": t["normal_hedef"],
            "normal_hedef": t["normal_hedef"],
            "hafta_ici_gun": t["hafta_ici_gun"],
            "tatil_gun": t["tatil_gun"],
            "izin_gun": t["izin_gun"],
            "fazla_mesai_secili": p.get("fazla_mesai", False),
            "nobet_1_15": 0,
            "nobet_16_son": 0,
            "nobet_hedef_1_15": p.get("nobet_hedef_1_15") if p["personel_turu"] == "surucu" else None,
            "nobet_hedef_16_son": p.get("nobet_hedef_16_son") if p["personel_turu"] == "surucu" else None,
            "toplam_saat": 0,
            "toplam_nobet": 0,
            "cumartesi": 0,
            "pazar": 0,
            "hafta_sonu": 0,
            "tatil": 0,
            "gunduz": 0,
            "gece": 0,
            "surucu_24": 0,
            "saglikci_24": 0,
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


@api_router.get("/schedule/{yil}/{ay}/targets")
async def get_targets(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    personnel = await get_active_personnel_list(istasyon_id)
    leaves = await build_leaves_map(istasyon_id)
    tinfo = await build_targets(yil, ay, personnel, leaves)
    return {"yil": yil, "ay": ay, "targets": [
        {"personel_id": p["id"], "ad_soyad": p["ad_soyad"], **tinfo[p["id"]]} for p in personnel]}


@api_router.post("/personnel/fazla-mesai")
async def set_overtime(data: dict, istasyon_id: str = Depends(current_station)):
    ids = set(data.get("personel_ids", []))
    await db.personnel.update_many({"istasyon_id": istasyon_id}, {"$set": {"fazla_mesai": False}})
    if ids:
        await db.personnel.update_many({"istasyon_id": istasyon_id, "id": {"$in": list(ids)}}, {"$set": {"fazla_mesai": True}})
    return {"secili": len(ids)}


# ------------- holidays (global / tüm istasyonlar için ortak) -------------
@api_router.get("/holidays/{yil}")
async def list_holidays(yil: int, user: dict = Depends(get_current_user)):
    return await get_holidays(yil)


@api_router.post("/holidays")
async def add_holiday(data: HolidayCreate, user: dict = Depends(get_current_user)):
    date.fromisoformat(data.tarih)
    await db.holidays.delete_many({"tarih": data.tarih})
    obj = Holiday(tarih=data.tarih, ad=data.ad)
    await db.holidays.insert_one(obj.model_dump())
    return obj


@api_router.delete("/holidays/{hid}")
async def delete_holiday(hid: str, user: dict = Depends(get_current_user)):
    res = await db.holidays.delete_one({"id": hid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Tatil bulunamadı")
    return {"deleted": True}


# ------------- carryover (ay geçişi) -------------
@api_router.get("/carryover/{yil}/{ay}")
async def carryover_get(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    return await get_carryover(yil, ay, istasyon_id)


@api_router.put("/carryover/{yil}/{ay}")
async def carryover_set(yil: int, ay: int, data: CarryoverSet, istasyon_id: str = Depends(current_station)):
    gunler = [g.model_dump() for g in data.gunler
              if g.saglikci_1 or g.saglikci_2 or g.surucu_gunduz or g.surucu_gece or g.surucu_24]
    await db.carryover.update_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id},
                                  {"$set": {"yil": yil, "ay": ay, "istasyon_id": istasyon_id,
                                            "gunler": gunler, "updated_at": now_iso()}},
                                  upsert=True)
    return await get_carryover(yil, ay, istasyon_id)


# ------------- templates -------------
@api_router.get("/templates", response_model=List[Template])
async def list_templates(istasyon_id: str = Depends(current_station)):
    return await db.templates.find({"istasyon_id": istasyon_id}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api_router.post("/templates", response_model=Template)
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


@api_router.delete("/templates/{tid}")
async def delete_template(tid: str, istasyon_id: str = Depends(current_station)):
    res = await db.templates.delete_one({"id": tid, "istasyon_id": istasyon_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Şablon bulunamadı")
    return {"deleted": True}


@api_router.post("/templates/{tid}/apply")
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


# ------------- exports -------------
def _fmt_task_label(task: str) -> str:
    return {
        "saglikci_24": "Sağlıkçı 24s",
        "surucu_gunduz": "Sürücü 09-21",
        "surucu_gece": "Sürücü 21-09",
        "surucu_24": "Sürücü 24s",
    }.get(task, task)


@api_router.get("/schedule/{yil}/{ay}/export/excel")
async def export_excel(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

    doc = await db.schedules.find_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Liste yok")
    personnel = await get_active_personnel_list(istasyon_id)
    pmap = {p["id"]: p["ad_soyad"] for p in personnel}

    wb = Workbook()
    ws = wb.active
    ws.title = f"{yil}-{ay:02d}"
    headers = ["Tarih", "Gün", "Sağlıkçı 1", "Sağlıkçı 2", "Sürücü 09-21", "Sürücü 21-09", "24s Sürücü"]
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="0B2A4A")
        c.alignment = Alignment(horizontal="center")

    gunler_tr = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cts", "Paz"]
    for day in doc["gunler"]:
        d = date.fromisoformat(day["tarih"])
        row = [
            day["tarih"],
            gunler_tr[d.weekday()],
            pmap.get(day.get("saglikci_1") or "", ""),
            pmap.get(day.get("saglikci_2") or "", ""),
            pmap.get(day.get("surucu_gunduz") or "", ""),
            pmap.get(day.get("surucu_gece") or "", ""),
            pmap.get(day.get("surucu_24") or "", ""),
        ]
        ws.append(row)

    for col in ws.columns:
        max_len = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=nobet_{yil}_{ay:02d}.xlsx"},
    )


@api_router.get("/schedule/{yil}/{ay}/export/pdf")
async def export_pdf(yil: int, ay: int, istasyon_id: str = Depends(current_station)):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    doc_db = await db.schedules.find_one({"yil": yil, "ay": ay, "istasyon_id": istasyon_id}, {"_id": 0})
    if not doc_db:
        raise HTTPException(404, "Liste yok")
    personnel = await get_active_personnel_list(istasyon_id)
    pmap = {p["id"]: p["ad_soyad"] for p in personnel}

    font = _register_pdf_font()
    bold = f"{font}-Bold" if font != "Helvetica" else "Helvetica-Bold"
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    styles["Title"].fontName = bold
    elements = [Paragraph(f"<b>112 Nöbet Listesi - {yil}/{ay:02d}</b>", styles["Title"]), Spacer(1, 10)]

    gunler_tr = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cts", "Paz"]
    data = [["Tarih", "Gün", "Sağlıkçı 1", "Sağlıkçı 2", "Sürücü 09-21", "Sürücü 21-09", "24s Sürücü"]]
    for day in doc_db["gunler"]:
        d = date.fromisoformat(day["tarih"])
        data.append([
            day["tarih"],
            gunler_tr[d.weekday()],
            pmap.get(day.get("saglikci_1") or "", "-"),
            pmap.get(day.get("saglikci_2") or "", "-"),
            pmap.get(day.get("surucu_gunduz") or "", "-"),
            pmap.get(day.get("surucu_gece") or "", "-"),
            pmap.get(day.get("surucu_24") or "", "-"),
        ])

    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2A4A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), bold),
        ("FONTNAME", (0, 1), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ]))
    elements.append(t)
    pdf.build(elements)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=nobet_{yil}_{ay:02d}.pdf"},
    )


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    await db.users.create_index("kullanici_adi", unique=True)
    admin_user = os.environ.get("ADMIN_KULLANICI_ADI", "admin")
    admin_pass = os.environ.get("ADMIN_SIFRE", "admin123")
    admin_email = os.environ.get("ADMIN_EMAIL")
    existing = await db.users.find_one({"kullanici_adi": admin_user})
    if not existing:
        u = User(kullanici_adi=admin_user, role="admin", email=admin_email, sifre_degistirildi=False)
        doc = u.model_dump()
        doc["password_hash"] = hash_password(admin_pass)
        await db.users.insert_one(doc)
        logger.info("Admin kullanıcısı oluşturuldu: %s", admin_user)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
