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


def _is_24h_driver_preference(pref: str) -> bool:
    return pref in ("24", "24_saat_surucu")


DRIVER_TASKS = {"surucu_gunduz", "surucu_gece", "surucu_24"}
PERIOD_LABELS = {1: "1-15", 2: "16-son"}


def _period_index_for_day(d: date) -> int:
    return 1 if d.day <= 15 else 2


def _build_mandatory_driver_minimums(personnel: List[dict]) -> Dict[int, Dict[str, int]]:
    """Kişi bazında dönemlik zorunlu minimum sürücü nöbet sayıları."""
    minimums: Dict[int, Dict[str, int]] = {1: {}, 2: {}}
    for p in personnel:
        if not p.get("aktif", True):
            continue
        h1 = p.get("nobet_hedef_1_15")
        h2 = p.get("nobet_hedef_16_son")
        if h1 is not None:
            minimums[1][p["id"]] = max(0, int(h1))
        if h2 is not None:
            minimums[2][p["id"]] = max(0, int(h2))
    return minimums


def _driver_count_for_period(ctx: "SchedulerContext", pid: str, period_idx: int) -> int:
    return ctx.driver_half1_shifts.get(pid, 0) if period_idx == 1 else ctx.driver_half2_shifts.get(pid, 0)


def _driver_minimum_deficits(ctx: "SchedulerContext", minimums: Dict[int, Dict[str, int]], period_idx: int) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for pid, required in minimums.get(period_idx, {}).items():
        if pid not in ctx.personnel:
            continue
        current = _driver_count_for_period(ctx, pid, period_idx)
        deficit = max(0, int(required) - int(current))
        if deficit > 0:
            out[pid] = deficit
    return out


def _pick_best_driver_12(
    ctx: "SchedulerContext",
    candidates: List[str],
    d: date,
    task: str,
    max_gun_asiri: int,
    deficits: Dict[str, int],
):
    """12s sürücü atamalarında eksik minimumu olanları (en büyük açık önce) öne çıkarır."""
    valid = []
    for pid in candidates:
        ok, _ = ctx.can_assign(pid, d, task, max_gun_asiri)
        if ok:
            valid.append(pid)
    if not valid:
        return None

    max_deficit = max((deficits.get(pid, 0) for pid in valid), default=0)
    if max_deficit > 0:
        valid = [pid for pid in valid if deficits.get(pid, 0) == max_deficit]

    valid.sort(key=lambda pid: ctx.score_candidate(pid, d, task))
    return valid[0]


def _build_unmet_driver_minimum_messages(
    ctx: "SchedulerContext",
    minimums: Dict[int, Dict[str, int]],
) -> List[str]:
    messages: List[str] = []
    for period_idx in (1, 2):
        for pid, required in minimums.get(period_idx, {}).items():
            if pid not in ctx.personnel:
                continue
            actual = _driver_count_for_period(ctx, pid, period_idx)
            if actual < required:
                name = ctx.personnel[pid].get("ad_soyad", pid)
                messages.append(
                    f"{name}: {PERIOD_LABELS[period_idx]} dönemi zorunlu sürücü nöbeti tamamlanamadı ({actual}/{required})"
                )
    return messages


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
                 holidays: Optional[set] = None, targets: Optional[Dict[str, int]] = None,
                 saglikci_max_nobet_araligi: int = 4):
        # personnel: list of dicts with id, personel_turu, aktif, hedef_saat, ad_soyad
        self.personnel = {p["id"]: p for p in personnel if p.get("aktif", True)}
        self.leaves = leaves  # {pid: {date_iso: status}}
        self.holidays = holidays or set()  # iso date strings
        self.targets = targets or {}  # pid -> normal aylık hedef saat
        self.saglikci_max_nobet_araligi = max(1, int(saglikci_max_nobet_araligi or 4))
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
        self.half1_shifts: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.half2_shifts: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.driver_half1_shifts: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.driver_half2_shifts: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.overtime_shift_count: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.overtime_half1_count: Dict[str, int] = {pid: 0 for pid in self.personnel}
        self.overtime_half2_count: Dict[str, int] = {pid: 0 for pid in self.personnel}

    def preload_days(self, days: List[dict]):
        """Önceki aydan taşan nöbetleri (istatistik sayılmadan) dinlenme kontrolü için yükler."""
        for day in days:
            for slot, task in SLOT_TO_TASK.items():
                pid = day.get(slot)
                if pid and pid in self.personnel:
                    self.assign(pid, date.fromisoformat(day["tarih"]), task, count_stats=False)

    def _is_gap_constrained(self, pid: str) -> bool:
        tur = self.personnel.get(pid, {}).get("personel_turu")
        return tur in ("paramedik", "att", "saglikci", "saglikci_surucu")

    def _last_assignment_date(self, pid: str, before: Optional[date] = None) -> Optional[date]:
        entries = self.pid_assignments.get(pid, [])
        dates = [dd for (dd, _t, _s, _e) in entries if before is None or dd < before]
        if not dates:
            return None
        return max(dates)

    def gap_full_days_before(self, pid: str, d: date) -> Optional[int]:
        prev = self._last_assignment_date(pid, before=d)
        if prev is None:
            return None
        return max(0, (d - prev).days - 1)

    def requires_gap_assignment_today(self, pid: str, d: date) -> bool:
        if not self._is_gap_constrained(pid):
            return False
        gap = self.gap_full_days_before(pid, d)
        if gap is None:
            return False
        return gap >= self.saglikci_max_nobet_araligi

    def is_health_like(self, pid: str) -> bool:
        return self.personnel.get(pid, {}).get("personel_turu") in ("paramedik", "att", "saglikci", "saglikci_surucu")

    def mandatory_target_hours(self, pid: str) -> int:
        p = self.personnel.get(pid, {})
        return max(0, int(self.targets.get(pid, p.get("hedef_saat", 0) or 0)))

    def remaining_mandatory_hours(self, pid: str) -> int:
        return max(0, self.mandatory_target_hours(pid) - self.hours.get(pid, 0))

    def projected_hours(self, pid: str, task: str) -> int:
        return self.hours.get(pid, 0) + int(TASKS[task]["hours"])

    def assignment_creates_overtime(self, pid: str, task: str) -> bool:
        return self.projected_hours(pid, task) > self.mandatory_target_hours(pid)

    def overtime_period_count(self, pid: str, d: date) -> int:
        return self.overtime_half1_count.get(pid, 0) if d.day <= 15 else self.overtime_half2_count.get(pid, 0)

    # ---------- hard constraint checks ----------
    def can_assign(self, pid: str, d: date, task: str, max_gun_asiri: int = 3) -> Tuple[bool, str]:
        p = self.personnel.get(pid)
        if not p:
            return False, "Personel bulunamadı"
        turu = p["personel_turu"]

        # 1) role compatibility
        if task == "saglikci_24":
            if turu not in ("paramedik", "att", "saglikci", "saglikci_surucu"):
                return False, "Personel sağlıkçı görevine uygun değil"
        elif task in ("surucu_gunduz", "surucu_gece"):
            if turu not in ("surucu", "saglikci_surucu"):
                return False, "Personel sürücü görevine uygun değil"
        elif task == "surucu_24":
            if turu not in ("surucu", "saglikci_surucu"):
                return False, "24 saatlik sürücü görevi yalnızca sürücü personeline verilebilir"

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

        return True, ""

    def assign(self, pid: str, d: date, task: str, count_stats: bool = True):
        s, e = _task_datetime_range(d, task)
        self.pid_assignments[pid].append((d, task, s, e))
        if not count_stats:
            return
        if d.isoformat() in self.holidays:
            self.holiday_shifts[pid] += 1
        if d.day <= 15:
            self.half1_shifts[pid] += 1
            if task in DRIVER_TASKS:
                self.driver_half1_shifts[pid] += 1
        else:
            self.half2_shifts[pid] += 1
            if task in DRIVER_TASKS:
                self.driver_half2_shifts[pid] += 1
        hrs = int(TASKS[task]["hours"])
        self.hours[pid] += hrs
        self.total_shifts[pid] += 1
        if self.is_health_like(pid) and self.hours[pid] > self.mandatory_target_hours(pid):
            self.overtime_shift_count[pid] += 1
            if d.day <= 15:
                self.overtime_half1_count[pid] += 1
            else:
                self.overtime_half2_count[pid] += 1
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
        # 1b2) sürücü rolü için 1-15 / 16-ay sonu nöbet hedefi (soft)
        if p.get("personel_turu") == "surucu":
            hedef_half = p.get("nobet_hedef_1_15") if d.day <= 15 else p.get("nobet_hedef_16_son")
            if hedef_half is not None:
                cur = self.half1_shifts[pid] if d.day <= 15 else self.half2_shifts[pid]
                if cur >= hedef_half:
                    score += 40.0 + (cur - hedef_half) * 10.0
                else:
                    score -= (hedef_half - cur) * 4.0
        # 1c) sürücü tercihi (12s / 24s)
        tercih = p.get("surucu_tercihi", "yok")
        prefers_24_driver = _is_24h_driver_preference(tercih)
        if task == "surucu_24" and tercih == "12":
            score += 30.0
        if task in ("surucu_gunduz", "surucu_gece") and prefers_24_driver:
            score += 14.0
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
        if task == "surucu_24" and not prefers_24_driver:
            score += 15.0
        # 7) sağlıkçı ve sağlıkçı+sürücü için nöbet aralığı dengelemesi
        if self._is_gap_constrained(pid):
            gap_days = self.gap_full_days_before(pid, d)
            if gap_days is not None:
                score -= min(gap_days, self.saglikci_max_nobet_araligi + 2) * 6.0
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

    # Sağlıkçı nöbet aralığı kuralı: bugün atanmazsa sınırı aşacak personel önceliklidir.
    urgent = [pid for pid in valid if ctx.requires_gap_assignment_today(pid, d)]
    if urgent:
        valid = urgent

    # Sağlıkçı görevleri için zorunlu saat + fazla mesai tercih adaleti.
    if task == "saglikci_24":
        health_valid = [pid for pid in valid if ctx.is_health_like(pid)]
        if health_valid:
            mandatory_due = [pid for pid in health_valid if ctx.remaining_mandatory_hours(pid) > 0]
            if mandatory_due:
                max_remaining = max(ctx.remaining_mandatory_hours(pid) for pid in mandatory_due)
                valid = [pid for pid in mandatory_due if ctx.remaining_mandatory_hours(pid) == max_remaining]
            else:
                overtime_candidates = [pid for pid in health_valid if ctx.assignment_creates_overtime(pid, task)]
                wanting = [pid for pid in overtime_candidates if ctx.personnel[pid].get("fazla_mesai", False)]
                if wanting:
                    min_ot = min(ctx.overtime_shift_count[pid] for pid in wanting)
                    wanting = [pid for pid in wanting if ctx.overtime_shift_count[pid] == min_ot]
                    min_period_ot = min(ctx.overtime_period_count(pid, d) for pid in wanting)
                    valid = [pid for pid in wanting if ctx.overtime_period_count(pid, d) == min_period_ot]
                elif overtime_candidates:
                    # Fazla mesai istemeyen personele yalnızca son çarede yaz.
                    min_ot = min(ctx.overtime_shift_count[pid] for pid in overtime_candidates)
                    valid = [pid for pid in overtime_candidates if ctx.overtime_shift_count[pid] == min_ot]

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
    saglikci_max_nobet_araligi: int = 4,
) -> Tuple[MonthlySchedule, List[str]]:
    """
    Returns (MonthlySchedule, errors). errors non-empty means partial/failed.
    """
    ctx = SchedulerContext(
        personnel,
        leaves,
        holidays,
        targets,
        saglikci_max_nobet_araligi=saglikci_max_nobet_araligi,
    )
    ctx.preload_days(carryover_days or [])
    days = _iter_days(yil, ay)
    schedule = MonthlySchedule(yil=yil, ay=ay, gunler=[], assignments=[])
    errors: List[str] = []

    mandatory_driver_minimums = _build_mandatory_driver_minimums(personnel)

    # pre-compute candidate pools
    paramedik_ids = [pid for pid, p in ctx.personnel.items() if p["personel_turu"] == "paramedik"]
    att_ids = [pid for pid, p in ctx.personnel.items() if p["personel_turu"] == "att"]
    surucu_ids = [pid for pid, p in ctx.personnel.items() if p["personel_turu"] == "surucu"]
    legacy_health_ids = [pid for pid, p in ctx.personnel.items()
                         if p["personel_turu"] in ("saglikci", "saglikci_surucu")]
    legacy_mode = not paramedik_ids and not att_ids and bool(legacy_health_ids)

    # Eski kayıtlar, personel türleri yeni sınıflara taşınana kadar önceki algoritmayla çalışabilir.
    if legacy_mode:
        paramedik_ids = list(legacy_health_ids)
        att_ids = list(legacy_health_ids)
        surucu_12_ids = surucu_ids + [pid for pid in legacy_health_ids
                                      if ctx.personnel[pid]["personel_turu"] == "saglikci_surucu"]
        surucu_24_ids = [pid for pid in legacy_health_ids
                         if ctx.personnel[pid]["personel_turu"] == "saglikci_surucu"]
    else:
        surucu_12_ids = surucu_ids
        surucu_24_ids = list(surucu_ids)

    if not paramedik_ids:
        errors.append("Paramedik sayısı yetersiz (en az 1 aktif paramedik gerekli)")
    if not att_ids:
        errors.append("ATT sayısı yetersiz (en az 1 aktif ATT gerekli)")
    if not surucu_12_ids:
        errors.append("Sürücü sayısı yetersiz (hiç aktif sürücü yok)")

    if errors:
        return schedule, errors

    for d in days:
        day = ShiftDay(tarih=d.isoformat())

        # Step 1: bir paramedik ve bir ATT ata
        s1 = _pick_best(ctx, paramedik_ids, d, "saglikci_24", max_gun_asiri)
        if s1 is None:
            errors.append(f"{d.isoformat()}: Paramedik atanamadı")
        else:
            ctx.assign(s1, d, "saglikci_24")
            day.saglikci_1 = s1
            schedule.assignments.append(Assignment(
                tarih=d.isoformat(), personel_id=s1, gorev="saglikci_24",
                baslangic="08:00", bitis="08:00", saat=24))

        s2_pool = [p for p in att_ids if p != s1]
        s2 = _pick_best(ctx, s2_pool, d, "saglikci_24", max_gun_asiri)
        if s2 is None:
            errors.append(f"{d.isoformat()}: ATT atanamadı")
        else:
            ctx.assign(s2, d, "saglikci_24")
            day.saglikci_2 = s2
            schedule.assignments.append(Assignment(
                tarih=d.isoformat(), personel_id=s2, gorev="saglikci_24",
                baslangic="08:00", bitis="08:00", saat=24))

        # Step 2: sürücü ata
        used_pids = {s1, s2}
        period_idx = _period_index_for_day(d)
        deficits = _driver_minimum_deficits(ctx, mandatory_driver_minimums, period_idx)
        pending_minimums = bool(deficits)

        # Zorunlu minimumlar tamamlanana kadar 12h sürücü atamasını öncele.
        pool_g = [p for p in surucu_12_ids if p not in used_pids]
        gunduz = _pick_best_driver_12(ctx, pool_g, d, "surucu_gunduz", max_gun_asiri, deficits)
        pool_n = [p for p in surucu_12_ids if p not in used_pids and p != gunduz]
        gece = _pick_best_driver_12(ctx, pool_n, d, "surucu_gece", max_gun_asiri, deficits)

        if not pending_minimums:
            # Önceki davranış: 24s tercihli Sağlıkçı+Sürücü önce dener.
            pool_24_pref = [
                p for p in surucu_24_ids
                if p not in used_pids and _is_24h_driver_preference(ctx.personnel[p].get("surucu_tercihi", "yok"))
            ]
            s24_pref = _pick_best(ctx, pool_24_pref, d, "surucu_24", max_gun_asiri)
            if s24_pref:
                ctx.assign(s24_pref, d, "surucu_24")
                day.surucu_24 = s24_pref
                schedule.assignments.append(Assignment(
                    tarih=d.isoformat(), personel_id=s24_pref, gorev="surucu_24",
                    baslangic="08:00", bitis="08:00", saat=24))
                schedule.gunler.append(day)
                continue

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
            # 12h ikilisi kurulamıyorsa (hard kısıtlar nedeniyle) 24h fallback her zaman serbest.
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

    # Step 3: Sağlıkçı ve Sağlıkçı+Sürücü için maksimum nöbet aralığı kontrolü
    for pid, p in ctx.personnel.items():
        if p.get("personel_turu") not in ("paramedik", "att", "saglikci", "saglikci_surucu"):
            continue
        assigned_dates = sorted({dd for (dd, _t, _s, _e) in ctx.pid_assignments.get(pid, [])})
        if len(assigned_dates) < 2:
            continue
        for prev, cur in zip(assigned_dates, assigned_dates[1:]):
            gap = (cur - prev).days - 1
            if gap > ctx.saglikci_max_nobet_araligi:
                errors.append(
                    f"{p.get('ad_soyad', pid)}: {prev.isoformat()} ile {cur.isoformat()} arasında {gap} tam gün boşluk var "
                    f"(izin verilen en fazla: {ctx.saglikci_max_nobet_araligi})"
                )

    errors.extend(_build_unmet_driver_minimum_messages(ctx, mandatory_driver_minimums))

    for pid, p in ctx.personnel.items():
        if not ctx.is_health_like(pid):
            continue
        target_hours = ctx.mandatory_target_hours(pid)
        if target_hours <= 0:
            continue
        actual_hours = ctx.hours.get(pid, 0)
        if actual_hours < target_hours:
            errors.append(
                f"{p.get('ad_soyad', pid)}'in zorunlu mesai saati tamamlanamadı ({actual_hours}/{target_hours} saat)"
            )

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
    saglikci_max_nobet_araligi: int = 4,
) -> Tuple[bool, str]:
    """Validates changing a single slot manually against all hard rules."""
    if new_pid is None:
        return True, ""
    # rebuild context up to this schedule
    ctx = SchedulerContext(
        personnel,
        leaves,
        None,
        targets,
        saglikci_max_nobet_araligi=saglikci_max_nobet_araligi,
    )
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
    saglikci_max_nobet_araligi: int = 4,
) -> List[dict]:
    """Her dolu hücre için diğer tüm atamalara göre kural ihlali / tercih uyarısı üretir."""
    cells = []
    for day in schedule_doc.get("gunler", []):
        for slot, task in SLOT_TO_TASK.items():
            pid = day.get(slot)
            if pid:
                cells.append((day["tarih"], slot, task, pid))

    out = []
    mandatory_driver_minimums = _build_mandatory_driver_minimums(personnel)
    for tarih, slot, task, pid in cells:
        ctx = SchedulerContext(
            personnel,
            leaves,
            None,
            targets,
            saglikci_max_nobet_araligi=saglikci_max_nobet_araligi,
        )
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
    # Hücre bazlı ihlallere ek olarak dönemlik zorunlu sürücü minimumu ihlalleri.
    ctx_all = SchedulerContext(
        personnel,
        leaves,
        None,
        targets,
        saglikci_max_nobet_araligi=saglikci_max_nobet_araligi,
    )
    ctx_all.preload_days(carryover_days or [])
    for day in schedule_doc.get("gunler", []):
        dd = date.fromisoformat(day["tarih"])
        for slot, task in SLOT_TO_TASK.items():
            pid = day.get(slot)
            if pid and pid in ctx_all.personnel:
                ctx_all.assign(pid, dd, task)

    yil = int(schedule_doc.get("yil", 0) or 0)
    ay = int(schedule_doc.get("ay", 0) or 0)
    if yil and ay:
        for period_idx in (1, 2):
            for pid, required in mandatory_driver_minimums.get(period_idx, {}).items():
                if pid not in ctx_all.personnel:
                    continue
                actual = _driver_count_for_period(ctx_all, pid, period_idx)
                if actual < required:
                    out.append({
                        "tarih": f"{yil:04d}-{ay:02d}-{'01' if period_idx == 1 else '16'}",
                        "slot": f"surucu_minimum_{period_idx}",
                        "tur": "hard",
                        "mesaj": (
                            f"{ctx_all.personnel[pid].get('ad_soyad', pid)}: {PERIOD_LABELS[period_idx]} dönemi "
                            f"zorunlu sürücü nöbeti tamamlanamadı ({actual}/{required})"
                        ),
                    })

        for pid, p in ctx_all.personnel.items():
            if not ctx_all.is_health_like(pid):
                continue
            target_hours = ctx_all.mandatory_target_hours(pid)
            if target_hours <= 0:
                continue
            actual_hours = ctx_all.hours.get(pid, 0)
            if actual_hours < target_hours:
                out.append({
                    "tarih": f"{yil:04d}-{ay:02d}-01",
                    "slot": f"zorunlu_mesai_{pid}",
                    "tur": "hard",
                    "mesaj": f"{p.get('ad_soyad', pid)}'in zorunlu mesai saati tamamlanamadı ({actual_hours}/{target_hours} saat)",
                })

    return out
