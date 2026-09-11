import { useEffect, useMemo, useState } from "react";
import { api, MONTHS_TR, DAYS_TR } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, X } from "lucide-react";

// helper: days in month
function buildMonth(yil, ay) {
  const first = new Date(yil, ay - 1, 1);
  const last = new Date(yil, ay, 0);
  const days = [];
  const startWeekday = (first.getDay() + 6) % 7; // Monday=0
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
    await api.post("/leaves/bulk", {
      personel_id: selectedPid,
      tarihler: Array.from(selected),
      durum,
    });
    toast.success(durum === null ? "Seçim temizlendi" : "Kaydedildi");
    loadLeaves();
  };

  const prevMonth = () => {
    if (ay === 1) { setAy(12); setYil(yil - 1); } else setAy(ay - 1);
  };
  const nextMonth = () => {
    if (ay === 12) { setAy(1); setYil(yil + 1); } else setAy(ay + 1);
  };

  return (
    <div className="space-y-6" data-testid="leaves-page">
      <div>
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Personel Tercihleri</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight mt-1">İzinler / İstekler</h1>
        <p className="text-muted-foreground mt-1">Personel bazında yıllık izin ve nöbet istememe tercihleri</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Seçim</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col md:flex-row md:items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <div className="text-xs font-semibold text-muted-foreground mb-1">Personel</div>
            <Select value={selectedPid} onValueChange={setSelectedPid}>
              <SelectTrigger data-testid="leaves-personnel-select"><SelectValue placeholder="Personel seç..." /></SelectTrigger>
              <SelectContent>
                {personnel.map((p) => <SelectItem key={p.id} value={p.id}>{p.ad_soyad}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={prevMonth} data-testid="prev-month"><ChevronLeft className="w-4 h-4" /></Button>
            <div className="font-heading font-bold text-lg min-w-[140px] text-center" data-testid="leaves-month-label">{MONTHS_TR[ay-1]} {yil}</div>
            <Button variant="outline" size="icon" onClick={nextMonth} data-testid="next-month"><ChevronRight className="w-4 h-4" /></Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 sm:p-6">
          <div className="grid grid-cols-7 gap-1 sm:gap-2 mb-2">
            {DAYS_TR.map((d) => (
              <div key={d} className="text-xs font-bold uppercase tracking-wider text-muted-foreground text-center py-1">{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1 sm:gap-2">
            {days.map((d, i) => {
              if (!d) return <div key={i} />;
              const status = statusMap[d.iso];
              const isSelected = selected.has(d.iso);
              let cls = "border-border bg-card hover:bg-secondary";
              if (status === "yillik_izin") cls = "leave-cell-yillik";
              else if (status === "nobet_istemiyor") cls = "leave-cell-nobet";
              if (isSelected) cls += " ring-2 ring-primary";
              return (
                <button
                  key={d.iso}
                  data-testid={`day-${d.iso}`}
                  onClick={() => toggleSelect(d.iso)}
                  className={`aspect-square min-h-[44px] rounded-md border text-sm font-semibold transition-colors duration-150 ${cls}`}
                >
                  <div className="flex flex-col items-center justify-center h-full">
                    <span>{d.day}</span>
                    {status === "yillik_izin" && <span className="text-[10px] mt-0.5">İZİN</span>}
                    {status === "nobet_istemiyor" && <span className="text-[10px] mt-0.5">İST.</span>}
                  </div>
                </button>
              );
            })}
          </div>

          <div className="mt-4 flex flex-wrap gap-4 text-xs">
            <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded leave-cell-yillik border" /> Yıllık İzin</div>
            <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded leave-cell-nobet border" /> Nöbet İstemiyorum</div>
            <div className="flex items-center gap-1.5"><span className="w-3 h-3 rounded border bg-card" /> Tercih Yok</div>
          </div>

          <div className="mt-6 flex flex-col sm:flex-row gap-2">
            <div className="text-sm text-muted-foreground flex-1">Seçili: <strong data-testid="selected-count">{selected.size}</strong> gün</div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => setSelected(new Set())} disabled={!selected.size}>
                <X className="w-4 h-4 mr-1" /> Seçimi Kaldır
              </Button>
              <Button variant="outline" onClick={() => applyBulk(null)} disabled={!selected.size} data-testid="clear-leaves-btn">Temizle</Button>
              <Button className="bg-yellow-500 hover:bg-yellow-600 text-yellow-950" onClick={() => applyBulk("nobet_istemiyor")} disabled={!selected.size} data-testid="mark-nobet-istemiyor">
                Nöbet İstemiyorum
              </Button>
              <Button className="bg-green-600 hover:bg-green-700 text-white" onClick={() => applyBulk("yillik_izin")} disabled={!selected.size} data-testid="mark-yillik-izin">
                Yıllık İzin
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
