"""Nöbet tercihlerinin ve sürücü dengelemesinin scheduler seçimlerine uygulanması."""
from __future__ import annotations


def _driver_counts(ctx, pid):
    """Kişinin mevcut sürücü nöbet sayılarını döndürür."""
    return (
        ctx.gunduz_count.get(pid, 0),
        ctx.gece_count.get(pid, 0),
        ctx.surucu_24_count.get(pid, 0),
    )


def _same_driver_streak(ctx, pid, task, d):
    """Bugünden geriye doğru aynı 12 saatlik vardiyanın kesintisiz serisini sayar."""
    streak = 0
    cur = d
    while True:
        cur = cur.fromordinal(cur.toordinal() - 1)
        found = False
        for dd, t, _s, _e in ctx.pid_assignments.get(pid, []):
            if dd == cur and t == task:
                found = True
                break
        if not found:
            break
        streak += 1
    return streak


def _preferred_candidates(ctx, candidates, d):
    # Uygun alternatif varsa "nöbet istemiyorum" diyenleri geriye bırak.
    # Tercih mutlak yasak değildir; son uygun grup yalnızca istemeyenlerden
    # oluşuyorsa vardiyanın boş kalmaması için onlar da değerlendirilebilir.
    willing = [
        pid for pid in candidates
        if ctx.leaves.get(pid, {}).get(d.isoformat()) != "nobet_istemiyor"
    ]
    return willing or list(candidates)


def install_preference_rules() -> None:
    import scheduler

    if getattr(scheduler, "_preference_rules_installed", False):
        return

    original_pick_best = scheduler._pick_best
    original_can_assign = scheduler.SchedulerContext.can_assign

    def pick_best(ctx, candidates, d, task, max_gun_asiri):
        # Ortak scheduler önce gerçek uygunluğu, nöbet aralığını ve tercihleri
        # değerlendirir; burada aday havuzunu önceden daraltıp uygun kişileri kaybetmeyiz.
        return original_pick_best(ctx, list(candidates), d, task, max_gun_asiri)

    def can_assign(ctx, pid, d, task, max_gun_asiri=3):
        ok, msg = original_can_assign(ctx, pid, d, task, max_gun_asiri)
        if not ok:
            return ok, msg

        # Sürücüde aynı vardiyayı gereksiz yere 3+ gün arka arkaya vermeme.
        # 3 gündüz üst üste geldiyse sonraki sürücü nöbeti gündüz değil gece;
        # aynı şekilde 3 gece üst üste geldiyse sonraki 12 saatlik nöbet gündüz olur.
        if task in ("surucu_gunduz", "surucu_gece"):
            opposite = "surucu_gece" if task == "surucu_gunduz" else "surucu_gunduz"
            same_streak = _same_driver_streak(ctx, pid, task, d)
            if same_streak >= 3:
                has_opposite_option = any(
                    dd == d - scheduler.timedelta(days=1) and t == opposite
                    for dd, t, _s, _e in ctx.pid_assignments.get(pid, [])
                )
                # Önceki gün farklı vardiya yoksa bile aynı vardiyayı dördüncü kez engelle.
                return False, "Sürücü aynı vardiyayı 3 günden fazla üst üste tutamaz"

        return True, ""

    def pick_best_driver_12(ctx, candidates, d, task, max_gun_asiri, deficits):
        valid = []
        for pid in candidates:
            ok, _ = can_assign(ctx, pid, d, task, max_gun_asiri)
            if ok:
                valid.append(pid)
        if not valid:
            return None

        # Zorunlu dönem nöbet hedefi ve ardından eşit toplam dağılım,
        # tercih kayıtlarından önce gelir.
        max_deficit = max((deficits.get(pid, 0) for pid in valid), default=0)
        if max_deficit > 0:
            valid = [pid for pid in valid if deficits.get(pid, 0) == max_deficit]

        valid = _preferred_candidates(ctx, valid, d)

        def balance_key(pid):
            day_count, night_count, shift24 = _driver_counts(ctx, pid)
            total_driver = day_count + night_count + shift24

            # Önce toplam sürücü nöbet sayısı eşitlensin.
            # Sonra bu görevi verdikten sonraki gündüz/gece farkı en aza insin.
            projected_day = day_count + (1 if task == "surucu_gunduz" else 0)
            projected_night = night_count + (1 if task == "surucu_gece" else 0)
            projected_imbalance = abs(projected_day - projected_night)

            same_streak = _same_driver_streak(ctx, pid, task, d)
            return (
                total_driver,
                projected_imbalance,
                same_streak,
                ctx.score_candidate(pid, d, task),
            )

        valid.sort(key=balance_key)
        return valid[0]

    scheduler._pick_best = pick_best
    scheduler._pick_best_driver_12 = pick_best_driver_12
    scheduler.SchedulerContext.can_assign = can_assign
    scheduler._preference_rules_installed = True
