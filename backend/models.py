"""Pydantic models for the 112 Nöbet Listesi app."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
import uuid


PersonnelType = Literal["saglikci", "surucu", "saglikci_surucu"]
LeaveStatus = Literal["yillik_izin", "nobet_istemiyor"]
TaskKind = Literal["saglikci_24", "surucu_gunduz", "surucu_gece", "surucu_24"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# ---------------- Personnel ----------------
class Personnel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    ad_soyad: str
    personel_turu: PersonnelType
    aktif: bool = True
    hedef_saat: int = 180
    aciklama: str = ""
    created_at: str = Field(default_factory=now_iso)


class PersonnelCreate(BaseModel):
    ad_soyad: str
    personel_turu: PersonnelType
    aktif: bool = True
    hedef_saat: int = 180
    aciklama: str = ""


class PersonnelUpdate(BaseModel):
    ad_soyad: Optional[str] = None
    personel_turu: Optional[PersonnelType] = None
    aktif: Optional[bool] = None
    hedef_saat: Optional[int] = None
    aciklama: Optional[str] = None


# ---------------- Leave / Request ----------------
class LeaveRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    personel_id: str
    tarih: str  # YYYY-MM-DD
    durum: LeaveStatus


class LeaveBulkSet(BaseModel):
    personel_id: str
    tarihler: List[str]
    durum: Optional[LeaveStatus] = None  # None means clear


# ---------------- Assignments / Schedule ----------------
class Assignment(BaseModel):
    """A single task assigned to a personnel on a given date."""
    model_config = ConfigDict(extra="ignore")
    tarih: str  # YYYY-MM-DD
    personel_id: str
    gorev: TaskKind
    baslangic: str  # HH:MM
    bitis: str      # HH:MM (may be next day for 24h & night)
    saat: int       # duration in hours (12 or 24)


class ShiftDay(BaseModel):
    tarih: str
    saglikci_1: Optional[str] = None
    saglikci_2: Optional[str] = None
    surucu_gunduz: Optional[str] = None  # 09-21
    surucu_gece: Optional[str] = None    # 21-09
    surucu_24: Optional[str] = None      # 24h driver (fills both slots)


class MonthlySchedule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    yil: int
    ay: int  # 1-12
    gunler: List[ShiftDay] = []
    assignments: List[Assignment] = []
    ihlaller: List[str] = []  # rule violation messages
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class GenerateRequest(BaseModel):
    yil: int
    ay: int
    ignore_leave_ids: List[str] = []  # leave request ids to ignore
    max_gun_asiri: int = 3  # max shifts for gün aşırı çalışma sağlıkçı


class ManualUpdateRequest(BaseModel):
    yil: int
    ay: int
    tarih: str
    slot: Literal["saglikci_1", "saglikci_2", "surucu_gunduz", "surucu_gece", "surucu_24"]
    personel_id: Optional[str] = None  # None to clear
