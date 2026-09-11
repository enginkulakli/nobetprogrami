import { useEffect, useMemo, useState } from "react";
import { api, MONTHS_TR, DAYS_TR, PERSONNEL_LABELS, TASK_LABELS } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Sparkles, FileSpreadsheet, FileText, Pencil, AlertTriangle, Printer, Flag, ListX, LayoutTemplate, IdCard, Info, CheckCircle2, XCircle, ArrowLeftRight, Star } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { PersonnelCardDialog } from "@/components/schedule/PersonnelCardDialog";
import { Badge } from "@/components/ui/badge";
import { ConflictDialog } from "@/components/schedule/ConflictDialog";
import { CarryoverCard } from "@/components/schedule/CarryoverCard";
import { useTemplates, applyTemplate } from "@/components/TemplatesCard";

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
  const [holidays, setHolidays] = useState({});
  const [conflicts, setConflicts] = useState([]);
  const [hint, setHint] = useState(null);
  const [conflictOpen, setConflictOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [tplId, setTplId] = useState("");
  const [violations, setViolations] = useState({});
  const [cardOpen, setCardOpen] = useState(false);
  const [candidates, setCandidates] = useState(null);
  const { templates } = useTemplates();

  const pmap = useMemo(() => Object.fromEntries(personnel.map((p) => [p.id, p])), [personnel]);

  const loadPersonnel = () => api.get("/personnel").then((r) => setPersonnel(r.data));
  useEffect(() => { loadPersonnel(); }, []);
  useEffect(() => {
    api.get(`/holidays/${yil}`).then((r) => setHolidays(Object.fromEntries(r.data.map((h) => [h.tarih, h.ad]))));
  }, [yil]);

  const loadViolations = async () => {
    const r = await api.get(`/schedule/${yil}/${ay}/violations`);
    setViolations(Object.fromEntries(r.data.violations.map((v) => [`${v.tarih}|${v.slot}`, v])));
  };

  const loadSchedule = async () => {
    const r = await api.get(`/schedule/${yil}/${ay}`);
    if (r.data.exists) {
      setSchedule(r.data);
      setErrors(r.data.ihlaller || []);
      loadViolations();
    } else {
      setSchedule(null);
      setErrors([]);
      setViolations({});
    }
  };
  useEffect(() => { loadSchedule(); }, [yil, ay]);

  const generate = async (extra = {}) => {
    setLoading(true);
    try {
      const r = await api.post("/schedule/generate", { yil, ay, ...extra });
      setSchedule(r.data.schedule);
      setErrors(r.data.errors || []);
      setConflicts(r.data.conflicts || []);
      setHint(r.data.ipucu || null);
      loadViolations();
      setRefreshKey((k) => k + 1);
      if (r.data.success) {
        setConflictOpen(false);
        toast.success(r.data.ignored?.length ? `Liste oluşturuldu (${r.data.ignored.length} istek göz ardı edildi)` : "Nöbet listesi oluşturuldu");
      } else {
        toast.warning(`${r.data.errors.length} sorun tespit edildi`);
        setConflictOpen(true);
      }
    } catch (e) {
      toast.error("Oluşturulamadı: " + (e.response?.data?.detail || e.message));
    } finally { setLoading(false); }
  };

  const doApplyTemplate = async () => {
    if (!tplId) return;
    try {
      await applyTemplate(tplId, yil, ay);
      loadPersonnel();
    } catch (e) { toast.error("Şablon uygulanamadı: " + e.message); }
  };

  const openEdit = (tarih, slot, currentPid, swap = false) => {
    setEditing({ tarih, slot, currentPid, swap });
    setCandidates(null);
    api.post("/schedule/candidates", { yil, ay, tarih, slot })
      .then((r) => setCandidates(r.data.adaylar))
      .catch(() => setCandidates([]));
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

  return (
    <TooltipProvider delayDuration={150}>
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
          {templates.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-muted-foreground mb-1">Şablon</div>
              <div className="flex gap-1">
                <Select value={tplId} onValueChange={setTplId}>
                  <SelectTrigger className="w-40" data-testid="schedule-template-select"><SelectValue placeholder="Şablon seç" /></SelectTrigger>
                  <SelectContent>
                    {templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.ad}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button variant="outline" onClick={doApplyTemplate} disabled={!tplId} data-testid="schedule-template-apply-btn" title="Şablonu bu aya uygula">
                  <LayoutTemplate className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
          <Button onClick={() => generate()} disabled={loading} data-testid="generate-btn">
            <Sparkles className="w-4 h-4 mr-2" /> {loading ? "Oluşturuluyor..." : "Oluştur"}
          </Button>
          {schedule && (
            <>
              <Button variant="outline" onClick={exportExcel} data-testid="export-excel-btn"><FileSpreadsheet className="w-4 h-4 mr-2" />Excel</Button>
              <Button variant="outline" onClick={exportPdf} data-testid="export-pdf-btn"><FileText className="w-4 h-4 mr-2" />PDF</Button>
              <Button variant="outline" onClick={() => window.print()} data-testid="print-btn"><Printer className="w-4 h-4 mr-2" />Yazdır</Button>
              <Button variant="outline" onClick={() => setCardOpen(true)} data-testid="personnel-card-btn"><IdCard className="w-4 h-4 mr-2" />Personel Kartı</Button>
            </>
          )}
        </div>
      </div>

      {errors.length > 0 && (
        <Card className="border-orange-300 bg-orange-50 no-print">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5" />
              <div className="flex-1">
                <div className="font-semibold text-orange-900">Uyarı: Bazı görevler atanamadı</div>
                <ul className="mt-2 text-sm text-orange-800 list-disc list-inside space-y-0.5 max-h-40 overflow-y-auto">
                  {errors.slice(0, 20).map((e, i) => <li key={i}>{e}</li>)}
                  {errors.length > 20 && <li>...ve {errors.length - 20} tane daha</li>}
                </ul>
              </div>
              <Button variant="outline" size="sm" className="border-orange-300 text-orange-900 hover:bg-orange-100" onClick={() => setConflictOpen(true)} data-testid="open-conflicts-btn">
                <ListX className="w-4 h-4 mr-2" /> Çakışan İstekleri Çöz
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <CarryoverCard yil={yil} ay={ay} personnel={personnel.filter((p) => p.aktif)} pmap={pmap} refreshKey={refreshKey} />

      {schedule?.yoksayilan_istekler?.length > 0 && (
        <div className="text-xs text-muted-foreground no-print" data-testid="ignored-info">
          Bu liste oluşturulurken {schedule.yoksayilan_istekler.length} istek göz ardı edildi.
        </div>
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
                    <TableHead className="w-40">Tarih</TableHead>
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
                    const holiday = holidays[day.tarih];
                    return (
                      <TableRow key={day.tarih} className={holiday ? "bg-red-50/70 dark:bg-red-950/20" : isWeekend ? "bg-secondary/60" : ""} data-testid={`row-${day.tarih}`}>
                        <TableCell className="font-mono text-xs">
                          <div className="flex items-center gap-1.5 whitespace-nowrap">
                            {day.tarih}
                            {holiday && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Badge variant="outline" className="bg-red-100 text-red-700 border-red-200 text-[10px] px-1.5 py-0 font-sans cursor-help" data-testid={`holiday-badge-${day.tarih}`}>
                                    <Flag className="w-2.5 h-2.5 mr-1" /> Tatil
                                  </Badge>
                                </TooltipTrigger>
                                <TooltipContent data-testid={`holiday-tooltip-${day.tarih}`}>{holiday}</TooltipContent>
                              </Tooltip>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="font-semibold text-xs">{DAYS_TR[(d.getDay() + 6) % 7]}</TableCell>
                        {SLOTS.map((s) => (
                          <SlotCell
                            key={s.key}
                            slot={s}
                            personName={pmap[day[s.key]]?.ad_soyad}
                            violation={violations[`${day.tarih}|${s.key}`]}
                            has24Driver={!!day.surucu_24}
                            onEdit={() => openEdit(day.tarih, s.key, day[s.key])}
                            onSwap={() => openEdit(day.tarih, s.key, day[s.key], true)}
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

      <ConflictDialog
        open={conflictOpen}
        onClose={() => setConflictOpen(false)}
        conflicts={conflicts}
        errors={errors}
        hint={hint}
        loading={loading}
        onRegenerate={(extra) => generate({ ...extra, ignore_leave_ids: [...(schedule?.yoksayilan_istekler || []), ...(extra.ignore_leave_ids || [])] })}
      />

      <PersonnelCardDialog open={cardOpen} onClose={() => setCardOpen(false)} yil={yil} ay={ay} personnel={personnel.filter((p) => p.aktif)} />

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent data-testid="edit-slot-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {editing?.swap && <ArrowLeftRight className="w-4 h-4 text-primary" />}
              {editing?.swap ? "Takas Önerisi: " : ""}{editing && SLOTS.find(s => s.key === editing.slot)?.label} - {editing?.tarih}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="text-sm text-muted-foreground">
              {editing?.swap ? "Kuralları bozmayan alternatifler önce listelenir; birine tıklayınca değişir." : "Personel seçin — uygunluk anında kontrol edilir:"}
            </div>
            <div className="max-h-80 overflow-y-auto space-y-1" data-testid="candidate-list">
              <button
                onClick={() => applyEdit(null)}
                className="w-full text-left px-3 py-2 rounded-md hover:bg-secondary text-sm"
                data-testid="clear-slot-btn"
              >
                — Boşalt —
              </button>
              {candidates === null && <div className="text-xs text-muted-foreground px-3 py-2">Kontrol ediliyor...</div>}
              {candidates && editing?.swap && !candidates.some((c) => c.uygun && !c.mevcut) && (
                <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2" data-testid="no-alternative-msg">
                  Kuralları bozmayan alternatif bulunamadı. Komşu günlerdeki atamaları değiştirmeyi veya görevi boşaltmayı deneyin.
                </div>
              )}
              {candidates?.map((c) => (
                <button
                  key={c.personel_id}
                  onClick={() => applyEdit(c.personel_id)}
                  disabled={!c.uygun && !c.mevcut}
                  data-testid={`assign-${c.personel_id}`}
                  data-uygun={c.uygun}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm flex items-center gap-2 ${
                    c.mevcut ? "bg-primary/10 font-semibold" : c.uygun ? "hover:bg-secondary" : "opacity-60 cursor-not-allowed"
                  }`}
                >
                  {c.uygun
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    : <XCircle className="w-4 h-4 text-red-500 shrink-0" />}
                  <span className="flex-1 min-w-0">
                    <span className="flex items-center gap-1.5">
                      {c.ad_soyad}
                      {c.onerilen && <Badge className="bg-emerald-600 text-white text-[10px] px-1.5 py-0 h-4"><Star className="w-2.5 h-2.5 mr-0.5" />Önerilen</Badge>}
                      {c.mevcut && <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">Mevcut</Badge>}
                    </span>
                    <span className={`block text-xs ${c.uygun ? "text-muted-foreground" : "text-red-600"}`} data-testid={`candidate-reason-${c.personel_id}`}>
                      {!c.uygun ? c.mesaj : c.tercih_uyarisi ? "Uygun · \"nöbet istemiyorum\" tercihi var" : "Uygun"}
                    </span>
                  </span>
                  <span className="text-xs text-muted-foreground font-mono shrink-0">{c.saat}/{c.hedef_saat}s</span>
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
    </TooltipProvider>
  );
}

function ViolationBadge({ violation, tarih, slot, onSwap }) {
  if (!violation) return null;
  const hard = violation.tur === "hard";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={onSwap}
          className={`inline-flex items-center justify-center w-4 h-4 rounded-full cursor-pointer hover:scale-110 transition-transform ${hard ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"}`}
          data-testid={`violation-badge-${tarih}-${slot}`}
        >
          {hard ? <AlertTriangle className="w-2.5 h-2.5" /> : <Info className="w-2.5 h-2.5" />}
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs" data-testid={`violation-tooltip-${tarih}-${slot}`}>
        <div className="text-xs font-semibold">{hard ? "Kural ihlali" : "Tercih uyarısı"}</div>
        <div className="text-xs">{violation.mesaj}</div>
        <div className="text-[10px] mt-1 opacity-80 flex items-center gap-1"><ArrowLeftRight className="w-2.5 h-2.5" /> Takas önerisi için tıklayın</div>
      </TooltipContent>
    </Tooltip>
  );
}

function SlotCell({ slot, personName, has24Driver, onEdit, onSwap, violation }) {
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
    <TableCell className={violation ? (violation.tur === "hard" ? "bg-red-50/60" : "bg-amber-50/60") : ""}>
      <button
        onClick={onEdit}
        className="group inline-flex items-center gap-1.5 text-sm hover:text-primary mr-1.5"
      >
        <span>{personName || <span className="text-muted-foreground italic">Boş</span>}</span>
        <Pencil className="w-3 h-3 opacity-0 group-hover:opacity-100" />
      </button>
      <ViolationBadge violation={violation} tarih={violation?.tarih} slot={slot.key} onSwap={onSwap} />
    </TableCell>
  );
}
