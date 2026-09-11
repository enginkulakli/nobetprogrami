from fastapi import APIRouter, HTTPException, Depends

from deps import db, require_admin
from models import Station, StationCreate, User, UserCreate, UserUpdate, AssignOrphansRequest
from auth import hash_password

router = APIRouter(prefix="/api", tags=["admin"])


# ------------- stations -------------
@router.get("/stations")
async def list_stations(user: dict = Depends(require_admin)):
    stations = await db.stations.find({}, {"_id": 0}).sort("ad", 1).to_list(1000)
    for s in stations:
        s["personel_sayisi"] = await db.personnel.count_documents({"istasyon_id": s["id"]})
    return stations


@router.post("/stations", response_model=Station)
async def create_station(data: StationCreate, user: dict = Depends(require_admin)):
    obj = Station(ad=data.ad)
    await db.stations.insert_one(obj.model_dump())
    return obj


@router.patch("/stations/{sid}")
async def update_station(sid: str, data: StationCreate, user: dict = Depends(require_admin)):
    res = await db.stations.update_one({"id": sid}, {"$set": {"ad": data.ad}})
    if res.matched_count == 0:
        raise HTTPException(404, "İstasyon bulunamadı")
    return await db.stations.find_one({"id": sid}, {"_id": 0})


@router.delete("/stations/{sid}")
async def delete_station(sid: str, user: dict = Depends(require_admin)):
    if await db.personnel.count_documents({"istasyon_id": sid}) or await db.users.count_documents({"istasyon_id": sid}):
        raise HTTPException(400, "İstasyona bağlı personel veya kullanıcı var; önce onları silin/taşıyın")
    res = await db.stations.delete_one({"id": sid})
    if res.deleted_count == 0:
        raise HTTPException(404, "İstasyon bulunamadı")
    return {"deleted": True}


# ------------- users / station managers -------------
@router.get("/users")
async def list_users(user: dict = Depends(require_admin)):
    users = await db.users.find({"role": "istasyon_sorumlusu"}, {"_id": 0, "password_hash": 0}).to_list(1000)
    stations = {s["id"]: s["ad"] for s in await db.stations.find({}, {"_id": 0}).to_list(1000)}
    for u in users:
        u["istasyon_ad"] = stations.get(u.get("istasyon_id"))
    return users


@router.post("/users")
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


@router.patch("/users/{uid}")
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


@router.delete("/users/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_admin)):
    res = await db.users.delete_one({"id": uid, "role": "istasyon_sorumlusu"})
    if res.deleted_count == 0:
        raise HTTPException(404, "Kullanıcı bulunamadı")
    return {"deleted": True}


# ------------- orphan data -------------
@router.get("/admin/orphans")
async def orphan_count(user: dict = Depends(require_admin)):
    q = {"$or": [{"istasyon_id": None}, {"istasyon_id": {"$exists": False}}]}
    return {
        "personnel": await db.personnel.count_documents(q),
        "leaves": await db.leaves.count_documents(q),
        "schedules": await db.schedules.count_documents(q),
    }


@router.post("/admin/assign-orphans")
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
