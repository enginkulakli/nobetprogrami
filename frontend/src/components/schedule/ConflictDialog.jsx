import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Shuffle, RefreshCw } from "lucide-react";
import { trDayShort } from "@/lib/api";

const DURUM = {
  yillik_izin: { label: "Yıllık İzin", cls: "bg-red-100 text-red-800 border-red-200" },
  nobet_istemiyor: { label: "Nöbet İstemiyor", cls: "bg-amber-100 text-amber-800 border-amber-200" },
};

export function ConflictDialog({ open, onClose, conflicts, errors, onRegenerate, loading, hint }) {
  const [selected, setSelected] = useState([]);
  useEffect(() => { if (open) setSelected([]); }, [open]);

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="conflict-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading">Çakışan İstekler</DialogTitle>
          <DialogDescription>
            {errors.length} gün/görev atanamadı. Aşağıdaki isteklerden göz ardı edileceklerini seçin ve listeyi yeniden oluşturun.
          </DialogDescription>
        </DialogHeader>

        {hint && (
          <div className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-md p-3" data-testid="conflict-hint">{hint}</div>
        )}

        {conflicts.length === 0 ? (
          <div className="text-sm text-muted-foreground p-4 rounded-md bg-secondary" data-testid="conflict-empty">
            Sorunlu günlerde izin/istek bulunamadı. Personel sayısı yetersiz olabilir; yeni personel ekleyin veya pasif personeli aktifleştirin.
          </div>
        ) : (
          <div className="max-h-80 overflow-y-auto divide-y divide-border rounded-md border border-border">
            {conflicts.map((c) => (
              <label key={c.id} className="flex items-center gap-3 px-3 py-2.5 hover:bg-secondary cursor-pointer" data-testid={`conflict-row-${c.id}`}>
                <Checkbox checked={selected.includes(c.id)} onCheckedChange={() => toggle(c.id)} data-testid={`conflict-check-${c.id}`} />
                <span className="font-mono text-xs w-28">{c.tarih} <span className="text-muted-foreground">{trDayShort(c.tarih)}</span></span>
                <span className="flex-1 text-sm font-medium">{c.ad_soyad}</span>
                <Badge variant="outline" className={DURUM[c.durum].cls}>{DURUM[c.durum].label}</Badge>
              </label>
            ))}
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={onClose} data-testid="conflict-close-btn">Kapat</Button>
          <Button variant="secondary" disabled={loading} onClick={() => onRegenerate({ rastgele_yoksay: true })} data-testid="conflict-random-btn">
            <Shuffle className="w-4 h-4 mr-2" /> Rastgele Göz Ardı Et
          </Button>
          <Button disabled={loading || selected.length === 0} onClick={() => onRegenerate({ ignore_leave_ids: selected })} data-testid="conflict-regenerate-btn">
            <RefreshCw className="w-4 h-4 mr-2" /> Seçilenleri Yoksay ve Oluştur ({selected.length})
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
