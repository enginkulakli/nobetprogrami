import os
import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from deps import db, client
from models import User
from auth import hash_password
from routers import (
    auth_router, admin_router, personnel_router,
    schedules_router, exports_router, holidays_router,
)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="112 Nöbet Listesi API")

app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(personnel_router.router)
app.include_router(schedules_router.router)
app.include_router(exports_router.router)
app.include_router(holidays_router.router)

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
