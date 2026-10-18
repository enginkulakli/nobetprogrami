"""Nöbet tercihlerinin scheduler seçimlerine uygulanması."""
from __future__ import annotations


def install_preference_rules() -> None:
    import scheduler

    if getattr(scheduler, "_preference_rules_installed", False):
        return

    original_pick_best = scheduler._pick_best
    original_pick_best_driver_12 = scheduler._pick_best_driver_12

    def preferred_candidates(ctx, candidates, d):
        date_iso = d.isoformat()
        wanted = [p for p in candidates if ctx.leaves.get(p, {}).get(date_iso) == "nobet_istiyor"]
        if wanted:
            return wanted
        available = [p for p in candidates if ctx.leaves.get(p, {}).get(date_iso) != "nobet_istemiyor"]
        return available or candidates

    def pick_best(ctx, candidates, d, task, max_gun_asiri):
        return original_pick_best(ctx, preferred_candidates(ctx, candidates, d), d, task, max_gun_asiri)

    def pick_best_driver_12(ctx, candidates, d, task, max_gun_asiri, deficits):
        return original_pick_best_driver_12(
            ctx, preferred_candidates(ctx, candidates, d), d, task, max_gun_asiri, deficits
        )

    scheduler._pick_best = pick_best
    scheduler._pick_best_driver_12 = pick_best_driver_12
    scheduler._preference_rules_installed = True
