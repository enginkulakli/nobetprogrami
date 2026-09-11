"""
Nöbet oluşturma algoritması (kural tabanlı sezgisel).
Merkezi constraint sistemi: hard_constraints ve soft_scoring.
İleride yeni kurallar için genişletilebilir modüler yapı.
"""
from __future__ import annotations
from calendar import monthrange
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
import random

from models import Assignment, ShiftDay, MonthlySchedule


SLOT_TO_TASK = {
    "saglikci_1": "saglikci_24",
    "saglikci_2": "saglikci_24",
    "surucu_gunduz": "surucu_gunduz",
    "surucu_gece": "surucu_gece",
    "surucu_24": "surucu_24",
}

# Task definitions
TASKS = {
    "saglikci_24":   {"start": "08:00", "end": "08:00", "hours": 24},
    "surucu_gunduz": {"start": "09:00", "end": "21:00", "hours": 12},
    "surucu_gece":   {"start": "21:00", "end": "09:00", "hours": 12},
    "surucu_24":     {"start": "08:00", "end": "08:00", "hours": 24},
}


def compute_normal_target(yil: int, ay: int, pid: str, leaves: Dict[str, Dict[str, str]], holidays: set) -> dict:
    """Hafta içi gün × 8 − hafta içi resmi tatil − hafta içi yıllık izin."""
    weekdays = [d for d in _iter_days(yil, ay) if d.weekday() < 5]
    tatil = [d for d in weekdays if d.isoformat() in holidays]
    izin = [d for d in weekdays if d.isoformat() not in holidays
            and leaves.get(pid, {}).get(d.isoformat()) == "yillik_izin"]
    return {
        "hafta_ici_gun": len(weekdays),
        "tatil_gun": len(tatil),
        "izin_gun": len(izin),
        "normal_hedef": max(0, (len(weekdays) - len(tatil) - len(izin)) * 8),
    }


def _iter_days(yil: int, ay: int) -> List[date]:
    _, days_in_month = monthrange(yil, ay)
    return [date(yil, ay, d) for d in range(1, days_in_month + 1)]


def _task_datetime_range(d: date, task: str) -> Tuple[float, float]:
    """Returns (start_ts, end_ts) as hours since epoch of the given month start."""
    if task == "saglikci_24":
        # 08:00 same day -> 08:00 next day
        s = d.toordinal() * 24 + 8
        e = s + 24
    elif task == "surucu_gunduz":
        s = d.toordinal() * 24 + 9
        e = s + 12
    elif task == "surucu_gece":
        s = d.toordinal() * 24 + 21
        e = s + 12
    elif task == "surucu_24":
        s = d.toordinal() * 24 + 8
        e = s + 24
    else:
        raise ValueError(f"Unknown task: {task}")
    return float(s), float(e)


class SchedulerContext:
    """Tracks state during generation for hard-constraint checking & soft balancing."""
    def __init__(self, personnel: List[dict], leaves: Dict[str, Dict[str, str]],
                 holidays: Optional[set] = None, targets: Optional[Dict[str, int]] = None):
        # personnel: list of dicts with id, personel_turu, aktif, hedef_saat, ad_soyad
        self.personnel = {p["id"]: p for p in personnel if p.get("aktif", True)}
        self.leaves = leaves  # {pid: {date_iso: status}}
        self.holidays = holidays or set()  # iso date strings
        self.targets = targets or {}  # pid -> normal aylık hedef saat
        # per-personnel tracking
        self.pid_assignments: Dict[str, List[Tuple[date, str, float, float]]] = {
            pid: [] for pid in self.personnel
        }
        self.hours: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.total_shifts: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.weekend_shifts: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.saturday: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.sunday: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.gunduz_count: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.gece_count: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.surucu_24_count: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.saglikci_24_count: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.holiday_shifts: Dict[str, int] = {pid: 0 for pid in self.personnel}

    def preload_days(self, days: List[dict]):
        """Önceki aydan taşan nöbetleri (istatistik sayılmadan) dinlenme kontrolü için yükler."""
        for day in days:
            for slot, task in SLOT_TO_TASK.items():
                pid = day.get(slot)
                if pid and pid in self.personnel:
                    self.assign(pid, date.fromisoformat(day["tarih"]), task, count_stats=False)

    # ---------- hard constraint checks ----------
    def can_assign(self, pid: str, d: date, task: str, max_gun_asiri: int = 3) -> Tuple[bool, str]:
        p = self.personnel.get(pid)
        if not p:
            return False, "Personel bulunamadı"
        turu = p["personel_turu"]

        # 1) role compatibility
        if task == "saglikci_24":
            if turu not in ("saglikci", "saglikci_surucu"):
                return False, "Personel sağlıkçı görevine uygun değil"
        elif task in ("surucu_gunduz", "surucu_gece"):
            if turu not in ("surucu", "saglikci_surucu"):
                return False, "Personel sürücü görevine uygun değil"
        elif task == "surucu_24":
            if turu != "saglikci_surucu":
                return False, "24 saatlik sürücü yalnızca Sağlıkçı+Sürücü olabilir"

        # 2) yıllık izin (hard)
        date_iso = d.isoformat()
        status = self.leaves.get(pid, {}).get(date_iso)
        if status == "yillik_izin":
            return False, "Yıllık izin günü"

        # 3) 12-saat dinlenme kuralı (all vardiya kombinasyonları)
        s_new, e_new = _task_datetime_range(d, task)
        for (_dd, _t, s_old, e_old) in self.pid_assignments[pid]:
            # overlap check
            if not (e_new <= s_old or s_new >= e_old):
                return False, "Görevler çakışıyor"
            # rest gap: min 12 saat both sides
            if s_new >= e_old:
                if s_new - e_old < 12:
                    return False, "Min 12 saat dinlenme kuralı ihlali"
            if s_old >= e_new:
                if s_old - e_new < 12:
                    return False, "Min 12 saat dinlenme kuralı ihlali"

        # 4) sağlıkçılar için 24 saatlik özel kurallar
        if task in ("saglikci_24", "surucu_24"):
            # arka arkaya iki gün 24h yasak, en az 1 tam gün boşluk
            for offset in (-1, 1):
                dd = d + timedelta(days=offset)
                for (dd2, t2, _s, _e) in self.pid_assignments[pid]:
                    if dd2 == dd and t2 in ("saglikci_24", "surucu_24"):
                        return False, "İki 24 saatlik nöbet arasında en az 1 tam gün gerekli"

            # aynı gün başka görev yok (rest kuralı ile zaten kapsanır ama açık kontrol)
            for (dd2, t2, _s, _e) in self.pid_assignments[pid]:
                if dd2 == d:
                    return False, "Aynı gün ikinci görev alınamaz"

            # gün aşırı max: aynı ay içerisinde toplam 24h nöbet limiti
            existing_24 = self.saglikci_24_count[pid] + self.surucu_24_count[pid]
            if existing_24 >= max_gun_asiri * 3:  # rahat limit; gerekirse azaltılır
                pass  # soft: yumuşak sınır, algoritma dengeleyecek

        # 5) sürücüler için 3 gün üst üste kuralı (12h vardiyalar için)
        if task in ("surucu_gunduz", "surucu_gece"):
            # son 3 gün art arda 12h vardiya var mı?
            consec = 0
            for offset in range(1, 4):
                dd = d - timedelta(days=offset)
                worked = any(
                    dd2 == dd and t2 in ("surucu_gunduz", "surucu_gece")
                    for (dd2, t2, _s, _e) in self.pid_assignments[pid]
                )
                if worked:
                    consec += 1
                else:
                    break
            if consec >= 3:
                return False, "Sürücü 3 günden fazla üst üste çalışamaz"

        # 6) fazla mesai: seçilmeyen personel normal hedefin üzerine çıkamaz
        if pid in self.targets and not p.get("fazla_mesai", False):
            if self.hours[pid] + int(TASKS[task]["hours"]) > self.targets[pid]:
                return False, "Normal çalışma hedefi doldu (fazla mesai seçili değil)"

        return True, ""

    def assign(self, pid: str, d: date, task: str, count_stats: bool = True):
        s, e = _task_datetime_range(d, task)
        self.pid_assignments[pid].append((d, task, s, e))
        if not count_stats:
            return
        if d.isoformat() in self.holidays:
            self.holiday_shifts[pid] += 1
        hrs = int(TASKS[task]["hours"])
        self.hours[pid] += hrs
        self.total_shifts[pid] += 1
        if d.weekday() == 5:
            self.saturday[pid] += 1
            self.weekend_shifts[pid] += 1
        elif d.weekday() == 6:
            self.sunday[pid] += 1
            self.weekend_shifts[pid] += 1
        if task == "surucu_gunduz":
            self.gunduz_count[pid] += 1
        elif task == "surucu_gece":
            self.gece_count[pid] += 1
        elif task == "surucu_24":
            self.surucu_24_count[pid] += 1
        elif task == "saglikci_24":
            self.saglikci_24_count[pid] += 1

    # ---------- soft scoring (lower = better) ----------
    def score_candidate(self, pid: str, d: date, task: str) -> float:
        p = self.personnel[pid]
        score = 0.0
        hedef = max(1, self.targets.get(pid, p.get("hedef_saat", 180)))
        # 1) çalışma saatleri dengesi (hedeften uzaklık)
        proj_hours = self.hours[pid] + TASKS[task]["hours"]
        score += (proj_hours / hedef) * 10.0
        # 1b) önce normal saatler dolsun; fazla mesai seçililer arasında adil dağılsın
        if proj_hours > hedef:
            overtime = proj_hours - hedef
            score += 60.0 + overtime * 1.0
        # 1c) sürücü tercihi (12s / 24s)
        tercih = p.get("surucu_tercihi", "yok")
        if task == "surucu_24" and tercih == "12":
            score += 30.0
        if task in ("surucu_gunduz", "surucu_gece") and tercih == "24":
            score += 10.0
        # 2) toplam nöbet sayısı
        score += self.total_shifts[pid] * 1.5
        # 3) hafta sonu dengesi
        if d.weekday() >= 5:
            score += self.weekend_shifts[pid] * 3.0
        # 3b) resmi tatil dengesi
        if d.isoformat() in self.holidays:
            score += self.holiday_shifts[pid] * 4.0
        # 4) gündüz/gece dengesi
        if task == "surucu_gunduz":
            score += self.gunduz_count[pid] * 1.5
        elif task == "surucu_gece":
            score += self.gece_count[pid] * 1.5
        # 5) nöbet istemiyor tercihi
        if self.leaves.get(pid, {}).get(d.isoformat()) == "nobet_istemiyor":
            score += 20.0
        # 6) 24h sürücü: tercih etmeyenler için soft ceza
        if task == "surucu_24" and tercih != "24":
            score += 15.0
        # tiebreaker: rastgele küçük
        score += random.random() * 0.01
        return score


def _pick_best(ctx: SchedulerContext, candidates: List[str], d: date, task: str, max_gun_asiri: int):
    valid = []
    for pid in candidates:
        ok, _ = ctx.can_assign(pid, d, task, max_gun_asiri)
        if ok:
            valid.append(pid)
    if not valid:
        return None
    valid.sort(key=lambda pid: ctx.score_candidate(pid, d, task))
    return valid[0]


def generate_schedule(
    yil: int,
    ay: int,
    personnel: List[dict],
    leaves: Dict[str, Dict[str, str]],
    max_gun_asiri: int = 3,
    holidays: Optional[set] = None,
    carryover_days: Optional[List[dict]] = None,
    targets: Optional[Dict[str, int]] = None,
) -> Tuple[MonthlySchedule, List[str]]:
    """
    Returns (MonthlySchedule, errors). errors non-empty means partial/failed.
    """
    ctx = SchedulerContext(personnel, leaves, holidays, targets)
    ctx.preload_days(carryover_days or [])
    days = _iter_days(yil, ay)
    schedule = MonthlySchedule(yil=yil, ay=ay, gunler=[], assignments=[])
    errors: List[str] = []

    # pre-compute candidate pools
    saglikci_ids = [pid for pid, p in ctx.personnel.items()
                    if p["personel_turu"] in ("saglikci", "saglikci_surucu")]
    surucu_12_ids = [pid for pid, p in ctx.personnel.items()
                     if p["personel_turu"] in ("surucu", "saglikci_surucu")]
    surucu_24_ids = [pid for pid, p in ctx.personnel.items()
                     if p["personel_turu"] == "saglikci_surucu"]

    if len(saglikci_ids) < 2:
        errors.append("Sağlıkçı sayısı yetersiz (en az 2 aktif sağlıkçı gerekli)")
    if not surucu_12_ids:
        errors.append("Sürücü sayısı yetersiz (hiç aktif sürücü yok)")

    if errors:
        return schedule, errors

    for d in days:
        day = ShiftDay(tarih=d.isoformat())

        # Step 1: 2 sağlıkçı ata
        s1 = _pick_best(ctx, saglikci_ids, d, "saglikci_24", max_gun_asiri)
        if s1 is None:
            errors.append(f"{d.isoformat()}: Sağlıkçı 1 atanamadı")
        else:
            ctx.assign(s1, d, "saglikci_24")
            day.saglikci_1 = s1
            schedule.assignments.append(Assignment(
                tarih=d.isoformat(), personel_id=s1, gorev="saglikci_24",
                baslangic="08:00", bitis="08:00", saat=24))

        s2_pool = [p for p in saglikci_ids if p != s1]
        s2 = _pick_best(ctx, s2_pool, d, "saglikci_24", max_gun_asiri)
        if s2 is None:
            errors.append(f"{d.isoformat()}: Sağlıkçı 2 atanamadı")
        else:
            ctx.assign(s2, d, "saglikci_24")
            day.saglikci_2 = s2
            schedule.assignments.append(Assignment(
                tarih=d.isoformat(), personel_id=s2, gorev="saglikci_24",
                baslangic="08:00", bitis="08:00", saat=24))

        # Step 2: sürücü ata - 24s tercihli Sağlıkçı+Sürücü varsa 24s; yoksa 12h iki vardiya, olmazsa 24h
        used_pids = {s1, s2}
        pool_24_pref = [p for p in surucu_24_ids if p not in used_pids
                        and ctx.personnel[p].get("surucu_tercihi") == "24"]
        s24_pref = _pick_best(ctx, pool_24_pref, d, "surucu_24", max_gun_asiri)
        if s24_pref:
            ctx.assign(s24_pref, d, "surucu_24")
            day.surucu_24 = s24_pref
            schedule.assignments.append(Assignment(
                tarih=d.isoformat(), personel_id=s24_pref, gorev="surucu_24",
                baslangic="08:00", bitis="08:00", saat=24))
            schedule.gunler.append(day)
            continue

        pool_g = [p for p in surucu_12_ids if p not in used_pids]
        gunduz = _pick_best(ctx, pool_g, d, "surucu_gunduz", max_gun_asiri)
        pool_n = [p for p in surucu_12_ids if p not in used_pids and p != gunduz]
        gece = _pick_best(ctx, pool_n, d, "surucu_gece", max_gun_asiri)

        if gunduz and gece:
            ctx.assign(gunduz, d, "surucu_gunduz")
            ctx.assign(gece, d, "surucu_gece")
            day.surucu_gunduz = gunduz
            day.surucu_gece = gece
            schedule.assignments.append(Assignment(
                tarih=d.isoformat(), personel_id=gunduz, gorev="surucu_gunduz",
                baslangic="09:00", bitis="21:00", saat=12))
            schedule.assignments.append(Assignment(
                tarih=d.isoformat(), personel_id=gece, gorev="surucu_gece",
                baslangic="21:00", bitis="09:00", saat=12))
        else:
            # fallback: 24h sürücü (sadece saglikci_surucu)
            pool_24 = [p for p in surucu_24_ids if p not in used_pids]
            s24 = _pick_best(ctx, pool_24, d, "surucu_24", max_gun_asiri)
            if s24:
                ctx.assign(s24, d, "surucu_24")
                day.surucu_24 = s24
                schedule.assignments.append(Assignment(
                    tarih=d.isoformat(), personel_id=s24, gorev="surucu_24",
                    baslangic="08:00", bitis="08:00", saat=24))
            else:
                errors.append(f"{d.isoformat()}: Sürücü atanamadı (12h yetersiz ve 24h alternatifi yok)")

        schedule.gunler.append(day)

    schedule.ihlaller = errors[:]
    return schedule, errors


def validate_manual_assignment(
    schedule_doc: dict,
    tarih: str,
    slot: str,
    new_pid: Optional[str],
    personnel: List[dict],
    leaves: Dict[str, Dict[str, str]],
    carryover_days: Optional[List[dict]] = None,
    targets: Optional[Dict[str, int]] = None,
) -> Tuple[bool, str]:
    """Validates changing a single slot manually against all hard rules."""
    if new_pid is None:
        return True, ""
    # rebuild context up to this schedule
    ctx = SchedulerContext(personnel, leaves, None, targets)
    ctx.preload_days(carryover_days or [])
    slot_to_task = SLOT_TO_TASK
    task_new = slot_to_task[slot]
    from datetime import date as _d
    dt_new = _d.fromisoformat(tarih)

    for day in schedule_doc.get("gunler", []):
        dd = _d.fromisoformat(day["tarih"])
        for s_slot, s_task in slot_to_task.items():
            pid = day.get(s_slot)
            if not pid:
                continue
            # skip the slot being replaced
            if day["tarih"] == tarih and s_slot == slot:
                continue
            ctx.assign(pid, dd, s_task)

    ok, msg = ctx.can_assign(new_pid, dt_new, task_new)
    return ok, msg


def compute_violations(
    schedule_doc: dict,
    personnel: List[dict],
    leaves: Dict[str, Dict[str, str]],
    carryover_days: Optional[List[dict]] = None,
    targets: Optional[Dict[str, int]] = None,
) -> List[dict]:
    """Her dolu hücre için diğer tüm atamalara göre kural ihlali / tercih uyarısı üretir."""
    cells = []
    for day in schedule_doc.get("gunler", []):
        for slot, task in SLOT_TO_TASK.items():
            pid = day.get(slot)
            if pid:
                cells.append((day["tarih"], slot, task, pid))

    out = []
    for tarih, slot, task, pid in cells:
        ctx = SchedulerContext(personnel, leaves, None, targets)
        ctx.preload_days(carryover_days or [])
        for t2, s2, task2, pid2 in cells:
            if (t2, s2) == (tarih, slot) or pid2 not in ctx.personnel:
                continue
            ctx.assign(pid2, date.fromisoformat(t2), task2, count_stats=(pid2 == pid))
        if pid not in ctx.personnel:
            out.append({"tarih": tarih, "slot": slot, "tur": "hard", "mesaj": "Personel pasif veya silinmiş"})
            continue
        ok, msg = ctx.can_assign(pid, date.fromisoformat(tarih), task)
        if not ok:
            out.append({"tarih": tarih, "slot": slot, "tur": "hard", "mesaj": msg})
        elif leaves.get(pid, {}).get(tarih) == "nobet_istemiyor":
            out.append({"tarih": tarih, "slot": slot, "tur": "soft", "mesaj": "\"Nöbet istemiyorum\" tercihi göz ardı edildi"})
    return out
