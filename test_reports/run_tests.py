import requests, json, sys, time

BASE = "https://shift-emergency.preview.emergentagent.com/api"
results = {"passed": [], "failed": []}

def rec_pass(name): results["passed"].append(name); print(f"PASS: {name}")
def rec_fail(name, evd, prio="HIGH"): results["failed"].append({"area": name, "issue": evd, "evidence": evd, "priority": prio}); print(f"FAIL: {name} :: {evd}")

# 1) health/root
r = requests.get(f"{BASE}/", timeout=15)
print("root:", r.status_code, r.text[:120])
if r.status_code == 200 and r.json().get("ok"): rec_pass("root")
else: rec_fail("root", f"{r.status_code} {r.text}")

# 2) seed demo
r = requests.post(f"{BASE}/seed/demo", timeout=20)
print("seed:", r.status_code, r.text[:200])
if r.status_code == 200: rec_pass("seed/demo")
else: rec_fail("seed/demo", f"{r.status_code} {r.text}")

# 3) list personnel
r = requests.get(f"{BASE}/personnel", timeout=15)
personnel = r.json() if r.status_code == 200 else []
print("personnel count:", len(personnel))
if r.status_code == 200 and len(personnel) >= 10: rec_pass(f"list personnel ({len(personnel)})")
else: rec_fail("personnel list", f"{r.status_code} count={len(personnel)}")

# 4) CRUD create/patch/delete
r = requests.post(f"{BASE}/personnel", json={"ad_soyad": "Test User", "personel_turu": "saglikci", "hedef_saat": 180}, timeout=15)
if r.status_code == 200:
    pid = r.json()["id"]; rec_pass("personnel create")
    r2 = requests.patch(f"{BASE}/personnel/{pid}", json={"ad_soyad": "Test User 2"}, timeout=15)
    if r2.status_code == 200 and r2.json()["ad_soyad"] == "Test User 2": rec_pass("personnel patch")
    else: rec_fail("personnel patch", f"{r2.status_code} {r2.text}")
    # Add a leave then delete personnel, verify cascade
    dates = ["2026-03-05", "2026-03-06"]
    requests.post(f"{BASE}/leaves/bulk", json={"personel_id": pid, "tarihler": dates, "durum": "yillik_izin"}, timeout=15)
    lv = requests.get(f"{BASE}/leaves", params={"personel_id": pid, "yil": 2026, "ay": 3}, timeout=15).json()
    print("leaves before del:", len(lv))
    rd = requests.delete(f"{BASE}/personnel/{pid}", timeout=15)
    lv2 = requests.get(f"{BASE}/leaves", params={"personel_id": pid, "yil": 2026, "ay": 3}, timeout=15).json()
    if rd.status_code == 200 and len(lv2) == 0: rec_pass("personnel delete + cascade leaves")
    else: rec_fail("cascade delete leaves", f"del={rd.status_code} remaining={len(lv2)}")
else:
    rec_fail("personnel create", f"{r.status_code} {r.text}")

# 5) leaves bulk + get with real personnel
if personnel:
    pid0 = personnel[0]["id"]
    dates = [f"2026-03-{d:02d}" for d in (10,11,12)]
    r = requests.post(f"{BASE}/leaves/bulk", json={"personel_id": pid0, "tarihler": dates, "durum": "yillik_izin"}, timeout=15)
    if r.status_code == 200 and r.json().get("added") == 3: rec_pass("leaves bulk set 3")
    else: rec_fail("leaves bulk", f"{r.status_code} {r.text}")
    r = requests.get(f"{BASE}/leaves", params={"personel_id": pid0, "yil": 2026, "ay": 3}, timeout=15)
    got = r.json() if r.status_code == 200 else []
    if r.status_code == 200 and len(got) >= 3: rec_pass(f"leaves list yil/ay ({len(got)})")
    else: rec_fail("leaves list", f"{r.status_code} n={len(got)}")

# 6) generate schedule
r = requests.post(f"{BASE}/schedule/generate", json={"yil": 2026, "ay": 3}, timeout=60)
print("generate:", r.status_code)
if r.status_code != 200:
    rec_fail("schedule generate", f"{r.status_code} {r.text[:300]}")
    print(json.dumps(results)); sys.exit(0)
gen = r.json()
print("success:", gen.get("success"), "errors:", gen.get("errors")[:3] if gen.get("errors") else [])
sched = gen["schedule"]
gunler = sched["gunler"]
assigns = sched["assignments"]

# All days filled correctly
all_filled = True
for day in gunler:
    if not (day.get("saglikci_1") and day.get("saglikci_2")):
        all_filled = False; break
    if not ((day.get("surucu_gunduz") and day.get("surucu_gece")) or day.get("surucu_24")):
        all_filled = False; break
if all_filled and gen.get("success"): rec_pass("schedule all days filled + success")
else: rec_fail("schedule fill", f"success={gen.get('success')} errors={gen.get('errors')[:2]}", "HIGH")

# 7) get saved schedule
r = requests.get(f"{BASE}/schedule/2026/3", timeout=15)
if r.status_code == 200 and r.json().get("exists"): rec_pass("get saved schedule exists")
else: rec_fail("get schedule", f"{r.status_code} {r.text[:200]}")

# 8) hard constraint: saglikci no back-to-back 24h
from collections import defaultdict
by_pid_24 = defaultdict(list)
for a in assigns:
    if a["gorev"] in ("saglikci_24", "surucu_24"):
        by_pid_24[a["personel_id"]].append(a["tarih"])
from datetime import date
viol = []
for pid, ds in by_pid_24.items():
    ds_sorted = sorted(ds)
    for i in range(len(ds_sorted)-1):
        d1 = date.fromisoformat(ds_sorted[i]); d2 = date.fromisoformat(ds_sorted[i+1])
        if (d2 - d1).days == 1:
            viol.append((pid, ds_sorted[i], ds_sorted[i+1]))
if not viol: rec_pass("no back-to-back 24h shifts")
else: rec_fail("back-to-back 24h", f"{viol[:3]}", "HIGH")

# 9) 12h rest between driver shifts: night day1 -> gunduz day2 forbidden
by_pid_drv = defaultdict(dict)
for a in assigns:
    if a["gorev"] in ("surucu_gunduz","surucu_gece"):
        by_pid_drv[a["personel_id"]][a["tarih"]] = a["gorev"]
viol2 = []
from datetime import timedelta
for pid, m in by_pid_drv.items():
    for tstr, task in m.items():
        if task == "surucu_gece":
            nxt = (date.fromisoformat(tstr) + timedelta(days=1)).isoformat()
            if m.get(nxt) == "surucu_gunduz":
                viol2.append((pid, tstr, nxt))
if not viol2: rec_pass("driver 12h rest respected")
else: rec_fail("12h rest gap", f"{viol2[:3]}", "HIGH")

# 10) leaves respected: check pid0 not scheduled on the leave dates
if personnel:
    leave_dates = [f"2026-03-{d:02d}" for d in (10,11,12)]
    bad = [a for a in assigns if a["personel_id"] == pid0 and a["tarih"] in leave_dates]
    if not bad: rec_pass("yillik_izin respected in generation")
    else: rec_fail("yillik_izin respected", f"bad={bad[:3]}", "HIGH")

# 11) manual assignment - rule violation: assign someone doing saglikci_24 on X to saglikci_24 on X+1
# Find such a case
saglikci_by_date = defaultdict(list)
for a in assigns:
    if a["gorev"] == "saglikci_24":
        saglikci_by_date[a["tarih"]].append(a["personel_id"])

# Pick a saglikci pid, find a date they're assigned, target next day, make sure they aren't already there
target = None
for pid, dates_list in [(pid, [a["tarih"] for a in assigns if a["personel_id"]==pid and a["gorev"]=="saglikci_24"]) for pid in set(a["personel_id"] for a in assigns if a["gorev"]=="saglikci_24")]:
    for dstr in dates_list:
        nxt = (date.fromisoformat(dstr) + timedelta(days=1)).isoformat()
        if nxt not in dates_list and any(day["tarih"]==nxt for day in gunler):
            # check pid is saglikci type
            pdoc = next((p for p in personnel if p["id"]==pid), None)
            if pdoc and pdoc["personel_turu"] in ("saglikci","saglikci_surucu"):
                target = (pid, nxt); break
    if target: break

if target:
    pid_t, nxt = target
    r = requests.post(f"{BASE}/schedule/manual", json={"yil":2026,"ay":3,"tarih":nxt,"slot":"saglikci_1","personel_id":pid_t}, timeout=15)
    j = r.json()
    print("manual violate:", j)
    if r.status_code==200 and j.get("success") is False and "hlal" in j.get("message",""): rec_pass("manual rule violation detected")
    else: rec_fail("manual rule violation", f"{r.status_code} {j}", "HIGH")
else:
    print("skip manual violation - no target found")

# 12) manual assignment success: swap two saglikci - use an eligible saglikci not on that day
# find a date and an eligible saglikci not on either slot & no conflict
success_done = False
for day in gunler:
    dstr = day["tarih"]
    current = {day.get("saglikci_1"), day.get("saglikci_2")}
    for p in personnel:
        if p["personel_turu"] not in ("saglikci","saglikci_surucu"): continue
        if p["id"] in current: continue
        # try assign to saglikci_1
        r = requests.post(f"{BASE}/schedule/manual", json={"yil":2026,"ay":3,"tarih":dstr,"slot":"saglikci_1","personel_id":p["id"]}, timeout=15)
        j = r.json() if r.status_code==200 else {}
        if r.status_code==200 and j.get("success"):
            rec_pass("manual assignment success (swap saglikci)"); success_done = True; break
    if success_done: break
if not success_done: rec_fail("manual success swap", "no valid swap found", "MEDIUM")

# 13) stats
r = requests.get(f"{BASE}/schedule/2026/3/stats", timeout=15)
if r.status_code==200:
    st = r.json()["stats"]
    keys_ok = st and all(k in st[0] for k in ("toplam_saat","toplam_nobet","hafta_sonu","cumartesi","pazar","gunduz","gece"))
    if keys_ok: rec_pass("stats endpoint")
    else: rec_fail("stats keys", f"{st[0] if st else 'empty'}")
else: rec_fail("stats", f"{r.status_code}")

# 14) Excel export
r = requests.get(f"{BASE}/schedule/2026/3/export/excel", timeout=30)
ct = r.headers.get("content-type","")
if r.status_code==200 and "spreadsheetml" in ct and len(r.content)>1000: rec_pass(f"excel export ({len(r.content)} bytes)")
else: rec_fail("excel export", f"{r.status_code} ct={ct} size={len(r.content)}", "HIGH")

# 15) PDF export
r = requests.get(f"{BASE}/schedule/2026/3/export/pdf", timeout=30)
ct = r.headers.get("content-type","")
if r.status_code==200 and "pdf" in ct and r.content[:4]==b"%PDF": rec_pass(f"pdf export ({len(r.content)} bytes)")
else: rec_fail("pdf export", f"{r.status_code} ct={ct}", "HIGH")

print("\n=== RESULTS ===")
print("PASS:", len(results["passed"]), "FAIL:", len(results["failed"]))
with open("/tmp/results.json","w") as f: json.dump(results,f,indent=2)
