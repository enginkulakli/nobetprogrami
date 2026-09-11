import { useEffect, useMemo, useState } from "react";
import { api, MONTHS_TR, DAYS_TR, PERSONNEL_LABELS, TASK_LABELS } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Sparkles, FileSpreadsheet, FileText, Pencil, AlertTriangle, Printer } from "lucide-react";

const SLOTS = [
  { key: "saglikci_1", label: "Sağlıkçı 1", role: "saglikci" },
  { key: "saglikci_2", label: "Sağlıkçı 2", role: "saglikci" },
  { key: "surucu_gunduz", label: "Sürücü 09-21", role: "surucu" },
  { key: "surucu_gece", label: "Sürücü 21-09", role: "surucu" },
  { key: "surucu_24", label: "24s Sürücü", role: "surucu_24" },
];

export default function Schedule() {
  const [personnel, setPersonnel] = useState([]);
  const [yil, setYil] = useState(new Date().getFullYear());
  const [ay, setAy] = useState(new Date().getMonth() + 1);
  const [schedule, setSchedule] = useState(null);
  const [errors, setErrors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null); // { tarih, slot, currentPid }

  const pmap = useMemo(() => Object.fromEntries(personnel.map((p) => [p.id, p])), [personnel]);

  useEffect(() => {
    api.get("/personnel").then((r) => setPersonnel(r.data));
  }, []);

  const loadSchedule = async () => {
    const r = await api.get(`/schedule/${yil}/${ay}`);
    if (r.data.exists) {
      setSchedule(r.data);
      setErrors(r.data.ihlaller || []);
    } else {
      setSchedule(null);
      setErrors([]);
    }
  };
  useEffect(() => { loadSchedule(); }, [yil, ay]);

  const generate = async () => {
    setLoading(true);
    try {
      const r = await api.post("/schedule/generate", { yil, ay });
      setSchedule(r.data.schedule);
      setErrors(r.data.errors || []);
      if (r.data.success) toast.success("Nöbet listesi oluşturuldu");
      else toast.warning(`${r.data.errors.length} sorun tespit edildi`);
    } catch (e) {
      toast.error("Oluşturulamadı: " + (e.response?.data?.detail || e.message));
    } finally { setLoading(false); }
  };

  const openEdit = (tarih, slot, currentPid) => {
    setEditing({ tarih, slot, currentPid });
  };

  const applyEdit = async (newPid) => {
    if (!editing) return;
    try {
      const res = await api.post("/schedule/manual", {
        yil, ay, tarih: editing.tarih, slot: editing.slot, personel_id: newPid || null,
      });
      if (!res.data.success) {
        toast.error(res.data.message || "Kural ihlali");
        return;
      }
      toast.success("Görev güncellendi");
      setEditing(null);
      loadSchedule();
    } catch (e) { toast.error("Hata: " + e.message); }
  };

  const exportExcel = () => window.open(`${api.defaults.baseURL}/schedule/${yil}/${ay}/export/excel`, "_blank");
  const exportPdf = () => window.open(`${api.defaults.baseURL}/schedule/${yil}/${ay}/export/pdf`, "_blank");

  const eligiblePersonnel = (slot) => {
    if (!editing) return [];
    if (slot === "saglikci_1" || slot === "saglikci_2") {
      return personnel.filter((p) => p.aktif && (p.personel_turu === "saglikci" || p.personel_turu === "saglikci_surucu"));
    }
    if (slot === "surucu_24") {
      return personnel.filter((p) => p.aktif && p.personel_turu === "saglikci_surucu");
    }
    return personnel.filter((p) => p.aktif && (p.personel_turu === "surucu" || p.personel_turu === "saglikci_surucu"));
  };

  return (
    <div className="space-y-6" data-testid="schedule-page">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 no-print">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Aylık Nöbet Planı</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight mt-1">Nöbet Listesi</h1>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <div className="text-xs font-semibold text-muted-foreground mb-1">Yıl</div>
            <Select value={String(yil)} onValueChange={(v) => setYil(Number(v))}>
              <SelectTrigger className="w-24" data-testid="schedule-year"><SelectValue /></SelectTrigger>
              <SelectContent>
                {[2024,2025,2026,2027].map(y=><SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="text-xs font-semibold text-muted-foreground mb-1">Ay</div>
            <Select value={String(ay)} onValueChange={(v) => setAy(Number(v))}>
              <SelectTrigger className="w-36" data-testid="schedule-month"><SelectValue /></SelectTrigger>
              <SelectContent>
                {MONTHS_TR.map((m,i)=><SelectItem key={i} value={String(i+1)}>{m}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={generate} disabled={loading} data-testid="generate-btn">
            <Sparkles className="w-4 h-4 mr-2" /> {loading ? "Oluşturuluyor..." : "Oluştur"}
          </Button>
          {schedule && (
            <>
              <Button variant="outline" onClick={exportExcel} data-testid="export-excel-btn"><FileSpreadsheet className="w-4 h-4 mr-2" />Excel</Button>
              <Button variant="outline" onClick={exportPdf} data-testid="export-pdf-btn"><FileText className="w-4 h-4 mr-2" />PDF</Button>
              <Button variant="outline" onClick={() => window.print()} data-testid="print-btn"><Printer className="w-4 h-4 mr-2" />Yazdır</Button>
            </>
          )}
        </div>
      </div>

      {errors.length > 0 && (
        <Card className="border-orange-300 bg-orange-50 no-print">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5" />
              <div>
                <div className="font-semibold text-orange-900">Uyarı: Bazı görevler atanamadı</div>
                <ul className="mt-2 text-sm text-orange-800 list-disc list-inside space-y-0.5 max-h-40 overflow-y-auto">
                  {errors.slice(0, 20).map((e, i) => <li key={i}>{e}</li>)}
                  {errors.length > 20 && <li>...ve {errors.length - 20} tane daha</li>}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {!schedule ? (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            Bu ay için nöbet listesi yok. "Oluştur" butonuna basın.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader className="no-print">
            <CardTitle className="font-heading">{MONTHS_TR[ay-1]} {yil}</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-24">Tarih</TableHead>
                    <TableHead className="w-16">Gün</TableHead>
                    <TableHead>Sağlıkçı 1</TableHead>
                    <TableHead>Sağlıkçı 2</TableHead>
                    <TableHead>Sürücü 09-21</TableHead>
                    <TableHead>Sürücü 21-09</TableHead>
                    <TableHead>24s Sürücü</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {schedule.gunler.map((day) => {
                    const d = new Date(day.tarih + "T00:00:00");
                    const isWeekend = d.getDay() === 0 || d.getDay() === 6;
                    return (
                      <TableRow key={day.tarih} className={isWeekend ? "bg-secondary/60" : ""}>
                        <TableCell className="font-mono text-xs">{day.tarih}</TableCell>
                        <TableCell className="font-semibold text-xs">{DAYS_TR[(d.getDay() + 6) % 7]}</TableCell>
                        {SLOTS.map((s) => (
                          <SlotCell
                            key={s.key}
                            slot={s}
                            personName={pmap[day[s.key]]?.ad_soyad}
                            has24Driver={!!day.surucu_24}
                            onEdit={() => openEdit(day.tarih, s.key, day[s.key])}
                          />
                        ))}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent data-testid="edit-slot-dialog">
          <DialogHeader>
            <DialogTitle>
              {editing && SLOTS.find(s => s.key === editing.slot)?.label} - {editing?.tarih}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="text-sm text-muted-foreground">Personel seçin:</div>
            <div className="max-h-80 overflow-y-auto space-y-1">
              <button
                onClick={() => applyEdit(null)}
                className="w-full text-left px-3 py-2 rounded-md hover:bg-secondary text-sm"
                data-testid="clear-slot-btn"
              >
                — Boşalt —
              </button>
              {editing && eligiblePersonnel(editing.slot).map((p) => (
                <button
                  key={p.id}
                  onClick={() => applyEdit(p.id)}
                  data-testid={`assign-${p.id}`}
                  className={`w-full text-left px-3 py-2 rounded-md hover:bg-secondary text-sm flex justify-between items-center ${
                    editing.currentPid === p.id ? "bg-primary/10 font-semibold" : ""
                  }`}
                >
                  <span>{p.ad_soyad}</span>
                  <span className="text-xs text-muted-foreground">{PERSONNEL_LABELS[p.personel_turu]}</span>
                </button>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>Kapat</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SlotCell({ slot, personName, has24Driver, onEdit }) {
  // hide 12h driver slots when 24h driver is set
  if (has24Driver && (slot.key === "surucu_gunduz" || slot.key === "surucu_gece")) {
    return <TableCell className="text-muted-foreground text-xs italic">— 24s aktif —</TableCell>;
  }
  // hide 24h driver cell when not set and 12h drivers exist
  if (!has24Driver && slot.key === "surucu_24") {
    return (
      <TableCell>
        <button onClick={onEdit} className="text-xs text-muted-foreground hover:text-primary underline underline-offset-2">
          — atama yok —
        </button>
      </TableCell>
    );
  }
  return (
    <TableCell>
      <button
        onClick={onEdit}
        className="group inline-flex items-center gap-1.5 text-sm hover:text-primary"
      >
        <span>{personName || <span className="text-muted-foreground italic">Boş</span>}</span>
        <Pencil className="w-3 h-3 opacity-0 group-hover:opacity-100" />
      </button>
    </TableCell>
  );
}
