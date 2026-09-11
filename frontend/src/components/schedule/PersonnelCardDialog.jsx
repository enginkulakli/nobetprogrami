import { useEffect, useState } from "react";
import { api, MONTHS_TR } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Copy, FileText, MessageCircle, Flag, ChevronLeft, ChevronRight, FolderArchive, Files } from "lucide-react";

export function PersonnelCardDialog({ open, onClose, yil, ay, personnel }) {
  const [pid, setPid] = useState("");
  const [card, setCard] = useState(null);

  useEffect(() => { if (open && !pid && personnel[0]) setPid(personnel[0].id); }, [open, personnel, pid]);
  useEffect(() => {
    if (!open || !pid) return;
    api.get(`/schedule/${yil}/${ay}/personnel/${pid}/card`).then((r) => setCard(r.data)).catch(() => setCard(null));
  }, [open, pid, yil, ay]);

  const copy = async () => {
    await navigator.clipboard.writeText(card.mesaj);
    toast.success("Mesaj kopyalandı");
  };
  const whatsapp = () => window.open(`https://wa.me/?text=${encodeURIComponent(card.mesaj)}`, "_blank");
  const pdf = () => window.open(`${api.defaults.baseURL}/schedule/${yil}/${ay}/personnel/${pid}/export/pdf`, "_blank");
  const allPdf = () => window.open(`${api.defaults.baseURL}/schedule/${yil}/${ay}/personnel-cards/export/pdf`, "_blank");
  const allZip = () => window.open(`${api.defaults.baseURL}/schedule/${yil}/${ay}/personnel-cards/export/zip`, "_blank");
  const idx = personnel.findIndex((p) => p.id === pid);
  const step = (d) => { const n = personnel[idx + d]; if (n) setPid(n.id); };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="personnel-card-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading">Personel Nöbet Kartı</DialogTitle>
          <DialogDescription>{MONTHS_TR[ay - 1]} {yil} — kişiye özel nöbet listesi; WhatsApp mesajı veya PDF olarak paylaşın.</DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => step(-1)} disabled={idx <= 0} data-testid="card-prev-btn"><ChevronLeft className="w-4 h-4" /></Button>
          <Select value={pid} onValueChange={setPid}>
            <SelectTrigger data-testid="card-personnel-select"><SelectValue placeholder="Personel seç" /></SelectTrigger>
            <SelectContent>
              {personnel.map((p) => <SelectItem key={p.id} value={p.id}>{p.ad_soyad}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon" onClick={() => step(1)} disabled={idx < 0 || idx >= personnel.length - 1} data-testid="card-next-btn"><ChevronRight className="w-4 h-4" /></Button>
        </div>
        <div className="text-xs text-muted-foreground -mt-1" data-testid="card-position">{idx + 1} / {personnel.length} personel</div>

        {card && (
          <div className="space-y-3">
            <div className="flex gap-2 text-xs">
              <Badge variant="secondary" data-testid="card-total-shifts">{card.toplam_nobet} nöbet</Badge>
              <Badge variant="secondary" data-testid="card-total-hours">{card.toplam_saat} saat</Badge>
            </div>
            <div className="max-h-64 overflow-y-auto rounded-md border border-border divide-y divide-border text-sm">
              {card.nobetler.length === 0 && <div className="p-4 text-center text-muted-foreground">Bu ay nöbeti yok.</div>}
              {card.nobetler.map((n) => (
                <div key={n.tarih + n.gorev} className={`flex items-center gap-3 px-3 py-2 ${n.hafta_sonu ? "bg-secondary/60" : ""}`} data-testid={`card-row-${n.tarih}`}>
                  <span className="font-mono text-xs w-24">{n.tarih}</span>
                  <span className="text-xs font-semibold w-8">{n.gun}</span>
                  <span className="flex-1">{n.gorev} <span className="text-muted-foreground text-xs">({n.saat_araligi})</span></span>
                  {n.tatil && <Badge variant="outline" className="bg-red-100 text-red-700 border-red-200 text-[10px]"><Flag className="w-2.5 h-2.5 mr-1" />{n.tatil}</Badge>}
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={whatsapp} className="bg-[#25D366] hover:bg-[#1ebe5b] text-white" data-testid="card-whatsapp-btn"><MessageCircle className="w-4 h-4 mr-2" /> WhatsApp</Button>
              <Button variant="outline" onClick={copy} data-testid="card-copy-btn"><Copy className="w-4 h-4 mr-2" /> Kopyala</Button>
              <Button variant="outline" onClick={pdf} data-testid="card-pdf-btn"><FileText className="w-4 h-4 mr-2" /> PDF</Button>
            </div>
          </div>
        )}
        <div className="border-t border-border pt-3">
          <div className="text-xs font-semibold text-muted-foreground mb-2">Toplu Gönderim — tüm personel</div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={allPdf} data-testid="card-all-pdf-btn"><Files className="w-4 h-4 mr-2" /> Tek PDF (sayfa/personel)</Button>
            <Button variant="secondary" size="sm" onClick={allZip} data-testid="card-all-zip-btn"><FolderArchive className="w-4 h-4 mr-2" /> ZIP (ayrı PDF'ler)</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
