from fastapi import APIRouter, HTTPException, Depends

from deps import db, get_current_user
from models import LoginRequest, ChangePasswordRequest
from auth import hash_password, verify_password, create_token

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/")
async def root():
    return {"message": "112 Nöbet Listesi API", "ok": True}


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/auth/login")
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


@router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    if user.get("istasyon_id"):
        st = await db.stations.find_one({"id": user["istasyon_id"]}, {"_id": 0})
        user["istasyon_ad"] = st["ad"] if st else None
    return user


@router.post("/auth/change-password")
async def change_password(data: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    full = await db.users.find_one({"id": user["id"]})
    if not full or not verify_password(data.eski_sifre, full.get("password_hash", "")):
        raise HTTPException(400, "Mevcut şifre hatalı")
    if len(data.yeni_sifre) < 4:
        raise HTTPException(400, "Yeni şifre en az 4 karakter olmalı")
    await db.users.update_one({"id": user["id"]},
                              {"$set": {"password_hash": hash_password(data.yeni_sifre), "sifre_degistirildi": True}})
    return {"success": True}
