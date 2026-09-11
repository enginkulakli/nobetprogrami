import { useEffect, useState } from "react";
import { api, MONTHS_TR, DAYS_TR } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { LayoutTemplate, Plus, Trash2, Play } from "lucide-react";

export function useTemplates() {
  const [templates, setTemplates] = useState([]);
  const load = () => api.get("/templates").then((r) => setTemplates(r.data));
  useEffect(() => { load(); }, []);
  return { templates, reload: load };
}

export async function applyTemplate(tid, yil, ay) {
  const r = await api.post(`/templates/${tid}/apply`, { yil, ay });
  toast.success(`Şablon uygulandı: ${r.data.personel_guncellendi} personel, ${r.data.tercih_eklendi} tercih eklendi`);
  return r.data;
}

export function TemplatesCard() {
  const { templates, reload } = useTemplates();
  const [open, setOpen] = useState(false);
  const [ad, setAd] = useState("");
  const [aciklama, setAciklama] = useState("");
  const now = new Date();
  const [kYil, setKYil] = useState(now.getFullYear());
  const [kAy, setKAy] = useState(now.getMonth() + 1);
  const [usePrefs, setUsePrefs] = useState(true);
  const [applyTo, setApplyTo] = useState({ yil: now.getFullYear(), ay: now.getMonth() + 1 });

  const create = async () => {
    if (!ad.trim()) return toast.error("Şablon adı gerekli");
    try {
      await api.post("/templates", { ad, aciklama, kaynak_yil: usePrefs ? kYil : null, kaynak_ay: usePrefs ? kAy : null });
      toast.success("Şablon kaydedildi");
      setOpen(false); setAd(""); setAciklama("");
      reload();
    } catch (e) { toast.error("Hata: " + e.message); }
  };

  const remove = async (id) => {
    await api.delete(`/templates/${id}`);
    toast.success("Şablon silindi");
    reload();
  };

  return (
    <Card data-testid="templates-card">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 font-heading"><LayoutTemplate className="w-5 h-5" /> Ekip Şablonları</CardTitle>
        <Button size="sm" onClick={() => setOpen(true)} data-testid="template-new-btn"><Plus className="w-4 h-4 mr-1" /> Yeni Şablon</Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">Mevcut personel düzeni (aktif/pasif, hedef saatler) ve tekrar eden "nöbet istemiyorum" tercihleri şablon olarak kaydedilir; yeni aya tek tıkla uygulanır.</p>
        <div className="flex flex-wrap items-end gap-2 text-xs">
          <span className="text-muted-foreground">Uygulanacak ay:</span>
          <Select value={String(applyTo.yil)} onValueChange={(v) => setApplyTo((a) => ({ ...a, yil: Number(v) }))}>
            <SelectTrigger className="w-24 h-8" data-testid="template-apply-year"><SelectValue /></SelectTrigger>
            <SelectContent>{[2024, 2025, 2026, 2027].map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={String(applyTo.ay)} onValueChange={(v) => setApplyTo((a) => ({ ...a, ay: Number(v) }))}>
            <SelectTrigger className="w-32 h-8" data-testid="template-apply-month"><SelectValue /></SelectTrigger>
            <SelectContent>{MONTHS_TR.map((m, i) => <SelectItem key={i} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        {templates.length === 0 ? (
          <div className="text-sm text-muted-foreground p-4 rounded-md bg-secondary text-center" data-testid="templates-empty">Henüz şablon yok.</div>
        ) : (
          <div className="divide-y divide-border rounded-md border border-border">
            {templates.map((t) => (
              <div key={t.id} className="p-3 flex flex-col sm:flex-row sm:items-center gap-2" data-testid={`template-row-${t.id}`}>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm">{t.ad}</div>
                  {t.aciklama && <div className="text-xs text-muted-foreground">{t.aciklama}</div>}
                  <div className="flex flex-wrap gap-1 mt-1">
                    <Badge variant="secondary">{t.personel.filter((p) => p.aktif).length} aktif personel</Badge>
                    <Badge variant="secondary">{t.tercihler.length} tekrar eden tercih</Badge>
                    {t.tercihler.slice(0, 4).map((p, i) => (
                      <Badge key={i} variant="outline" className="text-[10px]">{(t.personel.find((x) => x.personel_id === p.personel_id)?.ad_soyad || "?").split(" ")[0]} · {DAYS_TR[p.haftanin_gunu]}</Badge>
                    ))}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => applyTemplate(t.id, applyTo.yil, applyTo.ay)} data-testid={`template-apply-${t.id}`}><Play className="w-3.5 h-3.5 mr-1" /> Uygula</Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(t.id)} data-testid={`template-delete-${t.id}`}><Trash2 className="w-4 h-4 text-destructive" /></Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="template-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Yeni Şablon</DialogTitle>
            <DialogDescription>Mevcut personel düzeni kaydedilir. İsterseniz bir aydaki tekrar eden (≥2 kez, aynı haftanın günü) "nöbet istemiyorum" tercihleri de eklenir.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Input placeholder="Şablon adı (örn. Standart Ekip)" value={ad} onChange={(e) => setAd(e.target.value)} data-testid="template-name-input" />
            <Input placeholder="Açıklama (isteğe bağlı)" value={aciklama} onChange={(e) => setAciklama(e.target.value)} data-testid="template-desc-input" />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={usePrefs} onChange={(e) => setUsePrefs(e.target.checked)} data-testid="template-prefs-check" />
              Tekrar eden tercihleri şu aydan al:
            </label>
            {usePrefs && (
              <div className="flex gap-2">
                <Select value={String(kYil)} onValueChange={(v) => setKYil(Number(v))}>
                  <SelectTrigger className="w-24" data-testid="template-src-year"><SelectValue /></SelectTrigger>
                  <SelectContent>{[2024, 2025, 2026, 2027].map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}</SelectContent>
                </Select>
                <Select value={String(kAy)} onValueChange={(v) => setKAy(Number(v))}>
                  <SelectTrigger className="w-36" data-testid="template-src-month"><SelectValue /></SelectTrigger>
                  <SelectContent>{MONTHS_TR.map((m, i) => <SelectItem key={i} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>İptal</Button>
            <Button onClick={create} data-testid="template-save-btn">Kaydet</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
