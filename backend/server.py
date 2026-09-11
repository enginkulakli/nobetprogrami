from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import logging
from pathlib import Path
from typing import List, Optional
from calendar import monthrange
from datetime import date

from models import (
    Personnel, PersonnelCreate, PersonnelUpdate,
    LeaveRequest, LeaveBulkSet,
    MonthlySchedule, GenerateRequest, ManualUpdateRequest,
    new_id, now_iso,
)
from scheduler import generate_schedule, validate_manual_assignment, TASKS
from seed import DEMO_PERSONNEL

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


# ------------- helpers -------------
def strip_id(doc):
    if doc and "_id" in doc:
        doc.pop("_id", None)
    return doc


async def get_active_personnel_list() -> List[dict]:
    docs = await db.personnel.find({}, {"_id": 0}).to_list(1000)
    return docs


async def build_leaves_map(ignore_ids: Optional[List[str]] = None) -> dict:
    ignore = set(ignore_ids or [])
    leaves = {}
    async for d in db.leaves.find({}, {"_id": 0}):
        if d.get("id") in ignore:
            continue
        pid = d["personel_id"]
        leaves.setdefault(pid, {})[d["tarih"]] = d["durum"]
    return leaves


# ------------- root -------------
@api_router.get("/")
async def root():
    return {"message": "112 Nöbet Listesi API", "ok": True}


@api_router.get("/health")
async def health():
    return {"status": "ok"}


# ------------- seed -------------
@api_router.post("/seed/demo")
async def seed_demo():
    count = await db.personnel.count_documents({})
    if count > 0:
        return {"seeded": False, "existing": count}
    inserted = []
    for p in DEMO_PERSONNEL:
        obj = Personnel(**p)
        doc = obj.model_dump()
        await db.personnel.insert_one(doc)
        inserted.append(obj.id)
    return {"seeded": True, "count": len(inserted), "ids": inserted}


# ------------- personnel -------------
@api_router.get("/personnel", response_model=List[Personnel])
async def list_personnel():
    docs = await db.personnel.find({}, {"_id": 0}).to_list(1000)
    return docs


@api_router.post("/personnel", response_model=Personnel)
async def create_personnel(data: PersonnelCreate):
    obj = Personnel(**data.model_dump())
    await db.personnel.insert_one(obj.model_dump())
    return obj


@api_router.patch("/personnel/{pid}", response_model=Personnel)
async def update_personnel(pid: str, data: PersonnelUpdate):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(400, "Güncellenecek alan yok")
    res = await db.personnel.update_one({"id": pid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Personel bulunamadı")
    doc = await db.personnel.find_one({"id": pid}, {"_id": 0})
    return doc


@api_router.delete("/personnel/{pid}")
async def delete_personnel(pid: str):
    res = await db.personnel.delete_one({"id": pid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Personel bulunamadı")
    await db.leaves.delete_many({"personel_id": pid})
    return {"deleted": True}


# ------------- leaves / requests -------------
@api_router.get("/leaves")
async def list_leaves(personel_id: Optional[str] = None, yil: Optional[int] = None, ay: Optional[int] = None):
    q = {}
    if personel_id:
        q["personel_id"] = personel_id
    if yil and ay:
        prefix = f"{yil:04d}-{ay:02d}"
        q["tarih"] = {"$regex": f"^{prefix}"}
    docs = await db.leaves.find(q, {"_id": 0}).to_list(10000)
    return docs


@api_router.post("/leaves/bulk")
async def leaves_bulk(data: LeaveBulkSet):
    # remove existing entries for these dates & personnel
    await db.leaves.delete_many({"personel_id": data.personel_id, "tarih": {"$in": data.tarihler}})
    if data.durum is None:
        return {"cleared": len(data.tarihler)}
    new_docs = []
    for t in data.tarihler:
        lr = LeaveRequest(personel_id=data.personel_id, tarih=t, durum=data.durum)
        new_docs.append(lr.model_dump())
    if new_docs:
        await db.leaves.insert_many(new_docs)
    return {"added": len(new_docs)}


# ------------- schedules -------------
@api_router.get("/schedule/{yil}/{ay}")
async def get_schedule(yil: int, ay: int):
    doc = await db.schedules.find_one({"yil": yil, "ay": ay}, {"_id": 0})
    if not doc:
        return {"exists": False, "yil": yil, "ay": ay}
    return {"exists": True, **doc}


@api_router.post("/schedule/generate")
async def do_generate(req: GenerateRequest):
    personnel = await get_active_personnel_list()
    active = [p for p in personnel if p.get("aktif", True)]
    if len(active) < 3:
        raise HTTPException(400, "En az 3 aktif personel gerekli")
    leaves = await build_leaves_map(req.ignore_leave_ids)
    schedule, errors = generate_schedule(req.yil, req.ay, active, leaves, req.max_gun_asiri)
    doc = schedule.model_dump()
    doc["updated_at"] = now_iso()
    await db.schedules.update_one(
        {"yil": req.yil, "ay": req.ay},
        {"$set": doc},
        upsert=True,
    )
    return {"success": len(errors) == 0, "errors": errors, "schedule": doc}


@api_router.post("/schedule/manual")
async def manual_update(req: ManualUpdateRequest):
    doc = await db.schedules.find_one({"yil": req.yil, "ay": req.ay}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Nöbet listesi bulunamadı")

    personnel = await get_active_personnel_list()
    leaves = await build_leaves_map()

    if req.personel_id:
        ok, msg = validate_manual_assignment(doc, req.tarih, req.slot, req.personel_id, personnel, leaves)
        if not ok:
            return {"success": False, "message": f"Kural ihlali: {msg}"}

    # apply change
    updated = False
    for day in doc["gunler"]:
        if day["tarih"] == req.tarih:
            day[req.slot] = req.personel_id
            # remove existing assignment for this slot's task on this date & clean up
            slot_to_task = {
                "saglikci_1": "saglikci_24",
                "saglikci_2": "saglikci_24",
                "surucu_gunduz": "surucu_gunduz",
                "surucu_gece": "surucu_gece",
                "surucu_24": "surucu_24",
            }
            task = slot_to_task[req.slot]
            # For saglikci slots, remove assignment matching same task + matched removed pid
            new_assignments = []
            removed_once = False
            for a in doc.get("assignments", []):
                if (a["tarih"] == req.tarih and a["gorev"] == task and not removed_once
                        and (req.slot in ("saglikci_1", "saglikci_2")
                             or a["gorev"] == task)):
                    if req.slot in ("saglikci_1", "saglikci_2"):
                        # only remove one saglikci
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
    await db.schedules.update_one({"yil": req.yil, "ay": req.ay}, {"$set": doc})
    return {"success": True, "schedule": doc}


# ------------- statistics -------------
@api_router.get("/schedule/{yil}/{ay}/stats")
async def get_stats(yil: int, ay: int):
    doc = await db.schedules.find_one({"yil": yil, "ay": ay}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Liste yok")
    personnel = await get_active_personnel_list()
    pmap = {p["id"]: p for p in personnel}

    stats = {}
    for pid, p in pmap.items():
        stats[pid] = {
            "personel_id": pid,
            "ad_soyad": p["ad_soyad"],
            "personel_turu": p["personel_turu"],
            "hedef_saat": p.get("hedef_saat", 0),
            "toplam_saat": 0,
            "toplam_nobet": 0,
            "cumartesi": 0,
            "pazar": 0,
            "hafta_sonu": 0,
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

    return {"yil": yil, "ay": ay, "stats": list(stats.values())}


# ------------- exports -------------
def _fmt_task_label(task: str) -> str:
    return {
        "saglikci_24": "Sağlıkçı 24s",
        "surucu_gunduz": "Sürücü 09-21",
        "surucu_gece": "Sürücü 21-09",
        "surucu_24": "Sürücü 24s",
    }.get(task, task)


@api_router.get("/schedule/{yil}/{ay}/export/excel")
async def export_excel(yil: int, ay: int):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

    doc = await db.schedules.find_one({"yil": yil, "ay": ay}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Liste yok")
    personnel = await get_active_personnel_list()
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
async def export_pdf(yil: int, ay: int):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    doc_db = await db.schedules.find_one({"yil": yil, "ay": ay}, {"_id": 0})
    if not doc_db:
        raise HTTPException(404, "Liste yok")
    personnel = await get_active_personnel_list()
    pmap = {p["id"]: p["ad_soyad"] for p in personnel}

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
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
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
