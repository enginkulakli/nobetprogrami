from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends

from deps import db, current_station
from models import Personnel, PersonnelCreate, PersonnelUpdate, LeaveRequest, LeaveBulkSet
from seed import DEMO_PERSONNEL

router = APIRouter(prefix="/api", tags=["personnel"])


@router.post("/seed/demo")
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


@router.get("/personnel", response_model=List[Personnel])
async def list_personnel(istasyon_id: str = Depends(current_station)):
    return await db.personnel.find({"istasyon_id": istasyon_id}, {"_id": 0}).to_list(1000)


@router.post("/personnel", response_model=Personnel)
async def create_personnel(data: PersonnelCreate, istasyon_id: str = Depends(current_station)):
    obj = Personnel(istasyon_id=istasyon_id, **data.model_dump())
    await db.personnel.insert_one(obj.model_dump())
    return obj


@router.patch("/personnel/{pid}", response_model=Personnel)
async def update_personnel(pid: str, data: PersonnelUpdate, istasyon_id: str = Depends(current_station)):
    update = data.model_dump(exclude_unset=True)
    if not update:
        raise HTTPException(400, "Güncellenecek alan yok")
    res = await db.personnel.update_one({"id": pid, "istasyon_id": istasyon_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Personel bulunamadı")
    return await db.personnel.find_one({"id": pid}, {"_id": 0})


@router.delete("/personnel/{pid}")
async def delete_personnel(pid: str, istasyon_id: str = Depends(current_station)):
    res = await db.personnel.delete_one({"id": pid, "istasyon_id": istasyon_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Personel bulunamadı")
    await db.leaves.delete_many({"personel_id": pid, "istasyon_id": istasyon_id})
    return {"deleted": True}


@router.post("/personnel/fazla-mesai")
async def set_overtime(data: dict, istasyon_id: str = Depends(current_station)):
    ids = set(data.get("personel_ids", []))
    await db.personnel.update_many({"istasyon_id": istasyon_id}, {"$set": {"fazla_mesai": False}})
    if ids:
        await db.personnel.update_many({"istasyon_id": istasyon_id, "id": {"$in": list(ids)}},
                                       {"$set": {"fazla_mesai": True}})
    return {"secili": len(ids)}


# ------------- leaves / requests -------------
@router.get("/leaves")
async def list_leaves(istasyon_id: str = Depends(current_station),
                      personel_id: Optional[str] = None, yil: Optional[int] = None, ay: Optional[int] = None):
    q = {"istasyon_id": istasyon_id}
    if personel_id:
        q["personel_id"] = personel_id
    if yil and ay:
        q["tarih"] = {"$regex": f"^{yil:04d}-{ay:02d}"}
    return await db.leaves.find(q, {"_id": 0}).to_list(10000)


@router.post("/leaves/bulk")
async def leaves_bulk(data: LeaveBulkSet, istasyon_id: str = Depends(current_station)):
    p = await db.personnel.find_one({"id": data.personel_id, "istasyon_id": istasyon_id})
    if not p:
        raise HTTPException(404, "Personel bulunamadı")
    await db.leaves.delete_many({"personel_id": data.personel_id, "tarih": {"$in": data.tarihler}})
    if data.durum is None:
        return {"cleared": len(data.tarihler)}
    new_docs = [LeaveRequest(istasyon_id=istasyon_id, personel_id=data.personel_id, tarih=t, durum=data.durum).model_dump()
                for t in data.tarihler]
    if new_docs:
        await db.leaves.insert_many(new_docs)
    return {"added": len(new_docs)}
