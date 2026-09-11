from datetime import date
from fastapi import APIRouter, HTTPException, Depends

from deps import db, get_current_user
from models import HolidayCreate, Holiday
from helpers import get_holidays

router = APIRouter(prefix="/api", tags=["holidays"])


@router.get("/holidays/{yil}")
async def list_holidays(yil: int, user: dict = Depends(get_current_user)):
    return await get_holidays(yil)


@router.post("/holidays")
async def add_holiday(data: HolidayCreate, user: dict = Depends(get_current_user)):
    date.fromisoformat(data.tarih)
    await db.holidays.delete_many({"tarih": data.tarih})
    obj = Holiday(tarih=data.tarih, ad=data.ad)
    await db.holidays.insert_one(obj.model_dump())
    return obj


@router.delete("/holidays/{hid}")
async def delete_holiday(hid: str, user: dict = Depends(get_current_user)):
    res = await db.holidays.delete_one({"id": hid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Tatil bulunamadı")
    return {"deleted": True}
