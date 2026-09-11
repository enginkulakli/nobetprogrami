"""Authentication helpers: bcrypt hashing + JWT (Bearer) tokens."""
from __future__ import annotations
import os
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import HTTPException

JWT_ALG = "HS256"
TOKEN_DAYS = 7


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Oturum süresi doldu, tekrar giriş yapın")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Geçersiz oturum")
    if payload.get("type") != "access":
        raise HTTPException(401, "Geçersiz oturum türü")
    return payload
