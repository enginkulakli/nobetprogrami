"""Pydantic models for the 112 Nöbet Listesi app."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
import uuid

PersonnelType = Literal["paramedik", "att", "surucu", "saglikci", "saglikci_surucu"]
LeaveStatus = Literal["yillik_izin", "nobet_istemiyor", "nobet_istiyor"]
TaskKind = Literal["saglikci_24", "surucu_gunduz", "surucu_gece", "surucu_24"]
SurucuTercihi = Literal["12", "24", "24_saat_surucu", "yok"]
UserRole = Literal["admin", "istasyon_sorumlusu"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())

class Station(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    ad: str
    created_at: str = Field(default_factory=now_iso)

class StationCreate(BaseModel):
    ad: str

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    kullanici_adi: str
    role: UserRole = "istasyon_sorumlusu"
    istasyon_id: Optional[str] = None
    email: Optional[str] = None
    sifre_degistirildi: bool = False
    created_at: str = Field(default_factory=now_iso)

class UserCreate(BaseModel):
    kullanici_adi: str
    sifre: str
    istasyon_id: str

class UserUpdate(BaseModel):
    kullanici_adi: Optional[str] = None
    sifre: Optional[str] = None
    istasyon_id: Optional[str] = None

class LoginRequest(BaseModel):
    kullanici_adi: str
    sifre: str

class ChangePasswordRequest(BaseModel):
    eski_sifre: str
    yeni_sifre: str

class AssignOrphansRequest(BaseModel):
    istasyon_id: str

class Personnel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    istasyon_id: Optional[str] = None
    ad_soyad: str
    personel_turu: PersonnelType
    aktif: bool = True
    hedef_saat: int = 180
    aciklama: str = ""
    fazla_mesai: bool = False
    surucu_tercihi: SurucuTercihi = "yok"
    surucu_yapabilir: bool = False
    renk: str = ""
    nobet_hedef_1_15: Optional[int] = None
    nobet_hedef_16_son: Optional[int] = None
    created_at: str = Field(default_factory=now_iso)

class PersonnelCreate(BaseModel):
    ad_soyad: str
    personel_turu: PersonnelType
    aktif: bool = True
    hedef_saat: int = 180
    aciklama: str = ""
    fazla_mesai: bool = False
    surucu_tercihi: SurucuTercihi = "yok"
    surucu_yapabilir: bool = False
    renk: str = "#DCEBFA"
    nobet_hedef_1_15: Optional[int] = None
    nobet_hedef_16_son: Optional[int] = None

class PersonnelUpdate(BaseModel):
    ad_soyad: Optional[str] = None
    personel_turu: Optional[PersonnelType] = None
    aktif: Optional[bool] = None
    hedef_saat: Optional[int] = None
    aciklama: Optional[str] = None
    fazla_mesai: Optional[bool] = None
    surucu_tercihi: Optional[SurucuTercihi] = None
    surucu_yapabilir: Optional[bool] = None
    renk: Optional[str] = None
    nobet_hedef_1_15: Optional[int] = None
    nobet_hedef_16_son: Optional[int] = None

class LeaveRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    istasyon_id: Optional[str] = None
    personel_id: str
    tarih: str
    durum: LeaveStatus

class LeaveBulkSet(BaseModel):
    personel_id: str
    tarihler: List[str]
    durum: Optional[LeaveStatus] = None

class Assignment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tarih: str
    personel_id: str
    gorev: TaskKind
    baslangic: str
    bitis: str
    saat: int

class ShiftDay(BaseModel):
    tarih: str
    saglikci_1: Optional[str] = None
    saglikci_2: Optional[str] = None
    surucu_gunduz: Optional[str] = None
    surucu_gece: Optional[str] = None
    surucu_24: Optional[str] = None

class MonthlySchedule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    yil: int
    ay: int
    gunler: List[ShiftDay] = []
    assignments: List[Assignment] = []
    ihlaller: List[str] = []
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

class GenerateRequest(BaseModel):
    yil: int
    ay: int
    ignore_leave_ids: List[str] = []
    max_gun_asiri: int = 3
    rastgele_yoksay: bool = False
    saglikci_max_nobet_araligi: Optional[int] = None

class SchedulerSettings(BaseModel):
    saglikci_max_nobet_araligi: int = 4

class SchedulerSettingsUpdate(BaseModel):
    saglikci_max_nobet_araligi: int

class HolidayCreate(BaseModel):
    tarih: str
    ad: str

class Holiday(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    tarih: str
    ad: str
    kaynak: Literal["resmi", "ozel"] = "ozel"

class CarryoverSet(BaseModel):
    gunler: List[ShiftDay]

class TemplatePersonnel(BaseModel):
    personel_id: str
    ad_soyad: str
    aktif: bool
    hedef_saat: int

class TemplatePref(BaseModel):
    personel_id: str
    haftanin_gunu: int

class TemplateCreate(BaseModel):
    ad: str
    aciklama: str = ""
    kaynak_yil: Optional[int] = None
    kaynak_ay: Optional[int] = None

class Template(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    ad: str
    aciklama: str = ""
    personel: List[TemplatePersonnel] = []
    tercihler: List[TemplatePref] = []
    created_at: str = Field(default_factory=now_iso)

class TemplateApply(BaseModel):
    yil: int
    ay: int

class ManualUpdateRequest(BaseModel):
    yil: int
    ay: int
    tarih: str
    slot: Literal["saglikci_1", "saglikci_2", "surucu_gunduz", "surucu_gece", "surucu_24"]
    personel_id: Optional[str] = None
