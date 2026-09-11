"""Shared DB client and auth/authorization dependencies."""
from __future__ import annotations
import os
from pathlib import Path

from fastapi import Request, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from auth import decode_token

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]


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
