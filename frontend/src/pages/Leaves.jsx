import { useEffect, useMemo, useState } from "react";
import { api, MONTHS_TR, DAYS_TR, PERSONNEL_LABELS } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, X, Flag, Search, User } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

function buildMonth(yil, ay) {
  const first = new Date(yil, ay - 1, 1);
  const last = new Date(yil, ay, 0);
  const days = [];
  const startWeekday = (first.getDay() + 6) % 7;
  for (let i = 0; i < startWeekday; i++) days.push(null);
  for (let d = 1; d <= last.getDate(); d++) {
    const iso = `${yil}-${String(ay).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    days.push({ day: d, iso });
  }
  return days;
}

export default function Leaves() {
  const [personnel, setPersonnel] = useState([]);
  const [selectedPid, setSelectedPid] = useState("");
  const [yil, setYil] = useState(new Date().getFullYear());
  const [ay, setAy] = useState(new Date().getMonth() + 1);
  const [leaves, setLeaves] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [holidays, setHolidays] = useState({});
  const [filter, setFilter] = useState("");
  const [allLeaves, setAllLeaves] = useState([]);

  const loadAllLeaves = () => api.get(`/leaves?yil=${yil}&ay=${ay}`).then((r) => setAllLeaves(r.data));
  useEffect(() => { loadAllLeaves(); }, [yil, ay]);
  const leaveCounts = useMemo(() => {
    const m = {};
    allLeaves.forEach((x) => {
      m[x.personel_id] = m[x.personel_id] || { izin: 0, istek: 0, istiyor: 0 };
      if (x.durum === "yillik_izin") m[x.personel_id].izin += 1;
      else if (x.durum === "nobet_istiyor") m[x.personel_id].istiyor += 1;
      else m[x.personel_id].istek += 1;
    });
    return m;
  }, [allLeaves]);

  useEffect(() => {
    api.get(`/holidays/${yil}`).then((r) => setHolidays(Object.fromEntries(r.data.map((h) => [h.tarih, h.ad]))));
  }, [yil]);

  useEffect(() => {
    api.get("/personnel").then((r) => {
      setPersonnel(r.data);
      if (r.data.length && !selectedPid) setSelectedPid(r.data[0].id);
    });
  }, []);

  const loadLeaves = async () => {
    if (!selectedPid) return;
    const r = await api.get(`/leaves?personel_id=${selectedPid}&yil=${yil}&ay=${ay}`);
    setLeaves(r.data);
    setSelected(new Set());
  };
  useEffect(() => { loadLeaves(); }, [selectedPid, yil, ay]);

  const statusMap = useMemo(() => {
    const m = {};
    leaves.forEach((l) => { m[l.tarih] = l.durum; });
    return m;
  }, [leaves]);

  const days = useMemo(() => buildMonth(yil, ay), [yil, ay]);
  const toggleSelect = (iso) => {
    const s = new Set(selected);
    if (s.has(iso)) s.delete(iso); else s.add(iso);
    setSelected(s);
  };

  const applyBulk = async (durum) => {
    if (!selectedPid) return;
    if (selected.size === 0) { toast.error("En az bir gün seçin"); return; }
    await api.post("/leaves/bulk", { personel_id: selectedPid, tarihler: Array.from(selected), durum });
    toast.success(durum === null ? "Seçim temizlendi" : `${selected.size} gün kaydedildi`);
    loadLeaves();
    loadAllLeaves();
  };

  const prevMonth = () => {
    if (ay === 1) { setAy(12); setYil(yil - 1); } else setAy(ay - 1);
  };
  const nextMonth = () => {
    if (ay === 12) { setAy(1); setYil(yil + 1); } else setAy(ay + 1);
  };

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-6" data-testid="leaves-page">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Personel Tercihleri</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight mt-1">İzinler / İstekler</h1>
          <p className="text-muted-foreground mt-1">Yıllık izin, nöbet istememe ve mümkünse nöbet tutma tercihleri</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-4 items-start">
          <Card className="lg:sticky lg:top-4" data-testid="leaves-personnel-list">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-heading flex items-center gap-2"><User className="w-4 h-4" /> Personeller</CardTitle>
              <div className="relative mt-2"><Search className="w-4 h-4 absolute left-2.5 top-2.5 text-muted-foreground" /><Input placeholder="Ara..." value={filter} onChange={(e) => setFilter(e.target.value)} className="pl-8 h-9" /></div>
            </CardHeader>
            <CardContent className="p-2 max-h-[60vh] overflow-y-auto">
              {personnel.filter((p) => p.ad_soyad.toLowerCase().includes(filter.toLowerCase())).map((p) => {
                const c = leaveCounts[p.id];
                const active = p.id === selectedPid;
                return <button key={p.id} onClick={() => setSelectedPid(p.id)} className={`w-full text-left px-3 py-2 rounded-md flex items-center gap-3 ${active ? "bg-primary text-primary-foreground" : "hover:bg-secondary"}`}>
                  <div className="flex-1 min-w-0"><div className="text-sm font-semibold truncate">{p.ad_soyad}</div><div className={`text-[11px] ${active ? "text-primary-foreground/80" : "text-muted-foreground"}`}>{PERSONNEL_LABELS[p.personel_turu]}{!p.aktif && " · Pasif"}</div></div>
                  {c && <div className="flex gap-1 shrink-0">
                    {c.izin > 0 && <span className="text-[10px] font-bold px-1.5 rounded leave-cell-yillik">{c.izin}</span>}
                    {c.istek > 0 && <span className="text-[10px] font-bold px-1.5 rounded leave-cell-nobet">{c.istek}</span>}
                    {c.istiyor > 0 && <span className="text-[10px] font-bold px-1.5 rounded bg-green-100 text-green-800">{c.istiyor}</span>}
                  </div>}
                </button>;
              })}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <div><div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Seçili Personel</div><div className="font-heading font-bold text-lg">{personnel.find((p) => p.id === selectedPid)?.ad_soyad || "—"}</div></div>
                <div className="flex items-center gap-2"><Button variant="outline" size="icon" onClick={prevMonth}><ChevronLeft className="w-4 h-4" /></Button><div className="font-heading font-bold text-lg min-w-[140px] text-center">{MONTHS_TR[ay-1]} {yil}</div><Button variant="outline" size="icon" onClick={nextMonth}><ChevronRight className="w-4 h-4" /></Button></div>
              </div>
              <div className="grid grid-cols-7 gap-1 sm:gap-2 mb-2">{DAYS_TR.map((d) => <div key={d} className="text-xs font-bold uppercase tracking-wider text-muted-foreground text-center py-1">{d}</div>)}</div>
              <div className="grid grid-cols-7 gap-1 sm:gap-2">
                {days.map((d, i) => {
                  if (!d) return <div key={i} />;
                  const status = statusMap[d.iso];
                  const isSelected = selected.has(d.iso);
                  let cls = "border-border bg-card hover:bg-secondary";
                  if (status === "yillik_izin") cls = "leave-cell-yillik";
                  else if (status === "nobet_istemiyor") cls = "leave-cell-nobet";
                  else if (status === "nobet_istiyor") cls = "border-green-400 bg-green-50 text-green-800";
                  if (isSelected) cls += " ring-2 ring-primary";
                  const holiday = holidays[d.iso];
                  if (holiday && !status) cls += " border-red-300 bg-red-50";
                  const btn = <button key={d.iso} onClick={() => toggleSelect(d.iso)} className={`relative aspect-square min-h-[44px] w-full rounded-md border text-sm font-semibold ${cls}`}>
                    {holiday && <Flag className="absolute top-1 right-1 w-3 h-3 text-red-600" />}
                    <div className="flex flex-col items-center justify-center h-full"><span className={holiday ? "text-red-700" : ""}>{d.day}</span>{status === "yillik_izin" && <span className="text-[10px] mt-0.5">İZİN</span>}{status === "nobet_istemiyor" && <span className="text-[10px] mt-0.5">İST.</span>}{status === "nobet_istiyor" && <span className="text-[10px] mt-0.5">İSTİYOR</span>}</div>
                  </button>;
                  if (!holiday) return btn;
                  return <Tooltip key={d.iso}><TooltipTrigger asChild>{btn}</TooltipTrigger><TooltipContent>{holiday}</TooltipContent></Tooltip>;
                })}
              </div>

              <div className="mt-4 flex flex-wrap gap-4 text-xs">
                <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded leave-cell-yillik border" /> Yıllık İzin</div>
                <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded leave-cell-nobet border" /> Nöbet İstemiyorum</div>
                <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded border border-green-400 bg-green-50" /> Nöbet Tutmak İstiyorum</div>
                <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded border bg-card" /> Tercih Yok</div>
              </div>

              <div className="mt-6 flex flex-col sm:flex-row gap-2">
                <div className="text-sm text-muted-foreground flex-1">Seçili: <strong>{selected.size}</strong> gün</div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => setSelected(new Set())} disabled={!selected.size}><X className="w-4 h-4 mr-1" /> Seçimi Kaldır</Button>
                  <Button variant="outline" onClick={() => applyBulk(null)} disabled={!selected.size}>Temizle</Button>
                  <Button className="bg-yellow-500 hover:bg-yellow-600 text-yellow-950" onClick={() => applyBulk("nobet_istemiyor")} disabled={!selected.size}>Nöbet İstemiyorum</Button>
                  <Button className="bg-green-600 hover:bg-green-700 text-white" onClick={() => applyBulk("nobet_istiyor")} disabled={!selected.size}>Nöbet Tutmak İstiyorum</Button>
                  <Button className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => applyBulk("yillik_izin")} disabled={!selected.size}>Yıllık İzin</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </TooltipProvider>
  );
}
