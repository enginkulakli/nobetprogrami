import { useEffect, useState } from "react";
import { api, MONTHS_TR, trDayShort } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { ArrowRightLeft, Pencil } from "lucide-react";

const SLOTS = [
  { key: "saglikci_1", label: "Sağlıkçı 1", roles: ["saglikci", "saglikci_surucu"] },
  { key: "saglikci_2", label: "Sağlıkçı 2", roles: ["saglikci", "saglikci_surucu"] },
  { key: "surucu_gunduz", label: "Sürücü 09-21", roles: ["surucu", "saglikci_surucu"] },
  { key: "surucu_gece", label: "Sürücü 21-09", roles: ["surucu", "saglikci_surucu"] },
  { key: "surucu_24", label: "24s Sürücü", roles: ["saglikci_surucu"] },
];

const KAYNAK = {
  onceki_liste: { label: "Önceki ayın listesinden otomatik", cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  manuel: { label: "Manuel girildi", cls: "bg-sky-100 text-sky-800 border-sky-200" },
  yok: { label: "Bilgi yok", cls: "bg-amber-100 text-amber-800 border-amber-200" },
};

function lastDays(yil, ay, n = 3) {
  const dim = new Date(yil, ay, 0).getDate();
  return Array.from({ length: n }, (_, i) => `${yil}-${String(ay).padStart(2, "0")}-${String(dim - n + 1 + i).padStart(2, "0")}`);
}

export function CarryoverCard({ yil, ay, personnel, pmap, refreshKey }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState([]);

  const load = () => api.get(`/carryover/${yil}/${ay}`).then((r) => setData(r.data));
  useEffect(() => { load(); }, [yil, ay, refreshKey]);

  if (!data) return null;
  const k = KAYNAK[data.kaynak];

  const openEdit = () => {
    const dates = lastDays(data.onceki_yil, data.onceki_ay);
    const existing = Object.fromEntries((data.gunler || []).map((g) => [g.tarih, g]));
    setDraft(dates.map((t) => ({ tarih: t, ...(existing[t] || {}) })));
    setOpen(true);
  };

  const save = async () => {
    try {
      const r = await api.put(`/carryover/${yil}/${ay}`, { gunler: draft });
      setData(r.data);
      setOpen(false);
      toast.success("Ay geçiş bilgisi kaydedildi");
    } catch (e) { toast.error("Kaydedilemedi: " + e.message); }
  };

  return (
    <Card className="no-print" data-testid="carryover-card">
      <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-secondary grid place-items-center shrink-0">
          <ArrowRightLeft className="w-5 h-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-sm">Ay Geçişi: {MONTHS_TR[data.onceki_ay - 1]} {data.onceki_yil} son günleri</span>
            <Badge variant="outline" className={k.cls} data-testid="carryover-source">{k.label}</Badge>
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            {data.gunler.length > 0
              ? `${data.gunler.length} gün yüklendi — ilk günlerin 12s dinlenme ve arka arkaya 24s kuralları buna göre kontrol edilir.`
              : "Önceki ayın son nöbetleri bilinmiyor; ilk günlerde dinlenme kuralı eksik kontrol edilebilir."}
          </div>
        </div>
        {data.kaynak !== "onceki_liste" && (
          <Button variant="outline" size="sm" onClick={openEdit} data-testid="carryover-edit-btn">
            <Pencil className="w-3.5 h-3.5 mr-2" /> {data.kaynak === "manuel" ? "Düzenle" : "Elle Gir"}
          </Button>
        )}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl" data-testid="carryover-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Önceki Ayın Son Nöbetleri</DialogTitle>
            <DialogDescription>{MONTHS_TR[data.onceki_ay - 1]} {data.onceki_yil} — son 3 gün. Boş bırakılan alanlar yok sayılır.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 max-h-[60vh] overflow-y-auto">
            {draft.map((day, idx) => (
              <div key={day.tarih} className="rounded-md border border-border p-3">
                <div className="font-mono text-xs font-semibold mb-2">{day.tarih} <span className="text-muted-foreground">{trDayShort(day.tarih)}</span></div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {SLOTS.map((s) => (
                    <div key={s.key}>
                      <div className="text-[11px] text-muted-foreground mb-1">{s.label}</div>
                      <Select
                        value={day[s.key] || "none"}
                        onValueChange={(v) => setDraft((d) => d.map((x, i) => (i === idx ? { ...x, [s.key]: v === "none" ? null : v } : x)))}
                      >
                        <SelectTrigger className="h-8 text-xs" data-testid={`carry-${day.tarih}-${s.key}`}><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">— Boş —</SelectItem>
                          {personnel.filter((p) => s.roles.includes(p.personel_turu)).map((p) => (
                            <SelectItem key={p.id} value={p.id}>{p.ad_soyad}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>İptal</Button>
            <Button onClick={save} data-testid="carryover-save-btn">Kaydet</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
