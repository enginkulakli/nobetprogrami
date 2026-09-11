import { useEffect, useState } from "react";
import { api, PERSONNEL_LABELS } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Trash2, Pencil, UserPlus, Clock } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";

const emptyForm = { ad_soyad: "", personel_turu: "saglikci", aktif: true, hedef_saat: 180, aciklama: "", fazla_mesai: false, surucu_tercihi: "yok" };
const TERCIH_LABELS = { "12": "12s sürücü", "24": "24s sürücü", yok: "Tercih yok" };

export default function Personnel() {
  const [list, setList] = useState([]);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    const r = await api.get("/personnel");
    setList(r.data);
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setForm(emptyForm); setEditingId(null); setOpen(true); };
  const openEdit = (p) => {
    setForm({ ad_soyad: p.ad_soyad, personel_turu: p.personel_turu, aktif: p.aktif, hedef_saat: p.hedef_saat, aciklama: p.aciklama || "",
      fazla_mesai: !!p.fazla_mesai, surucu_tercihi: p.surucu_tercihi || "yok" });
    setEditingId(p.id);
    setOpen(true);
  };

  const save = async () => {
    if (!form.ad_soyad.trim()) { toast.error("Ad soyad gerekli"); return; }
    try {
      if (editingId) {
        await api.patch(`/personnel/${editingId}`, form);
        toast.success("Güncellendi");
      } else {
        await api.post("/personnel", form);
        toast.success("Eklendi");
      }
      setOpen(false); load();
    } catch (e) { toast.error("Hata: " + e.message); }
  };

  const toggleOvertime = async (p) => {
    await api.patch(`/personnel/${p.id}`, { fazla_mesai: !p.fazla_mesai });
    load();
  };

  const setAllOvertime = async (on) => {
    await api.post("/personnel/fazla-mesai", { personel_ids: on ? list.filter((x) => x.aktif).map((x) => x.id) : [] });
    toast.success(on ? "Tüm aktif personel fazla mesai için seçildi" : "Fazla mesai seçimleri kaldırıldı");
    load();
  };

  const remove = async (id) => {
    if (!window.confirm("Bu personel silinsin mi?")) return;
    await api.delete(`/personnel/${id}`);
    toast.success("Silindi");
    load();
  };

  return (
    <div className="space-y-6" data-testid="personnel-page">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Personel</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight mt-1">Personel Yönetimi</h1>
        </div>
        <Button onClick={openNew} data-testid="new-personnel-btn">
          <UserPlus className="w-4 h-4 mr-2" /> Yeni Personel
        </Button>
      </div>

      <Card data-testid="overtime-card">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 font-heading text-base"><Clock className="w-5 h-5 text-amber-600" /> Fazla Mesai Yapmak İsteyen Personeller</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">Önce tüm personelin normal çalışma saati (hafta içi gün × 8s − tatil − izin) doldurulur; kalan görevler yalnızca burada seçili personele fazla mesai olarak, adil biçimde dağıtılır.</p>
          <div className="flex flex-wrap gap-2">
            {list.filter((x) => x.aktif).map((x) => (
              <label key={x.id} className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm cursor-pointer transition-colors ${x.fazla_mesai ? "bg-amber-50 border-amber-300 text-amber-900" : "border-border hover:bg-secondary"}`} data-testid={`overtime-chip-${x.id}`}>
                <Checkbox checked={!!x.fazla_mesai} onCheckedChange={() => toggleOvertime(x)} data-testid={`overtime-check-${x.id}`} />
                {x.ad_soyad}
              </label>
            ))}
          </div>
          <div className="flex gap-2 text-xs">
            <Button size="sm" variant="outline" onClick={() => setAllOvertime(true)} data-testid="overtime-all-btn">Tümünü Seç</Button>
            <Button size="sm" variant="ghost" onClick={() => setAllOvertime(false)} data-testid="overtime-none-btn">Temizle</Button>
            <span className="self-center text-muted-foreground" data-testid="overtime-count">{list.filter((x) => x.fazla_mesai && x.aktif).length} personel seçili</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ad Soyad</TableHead>
                  <TableHead>Personel Türü</TableHead>
                  <TableHead>Sürücü Tercihi</TableHead>
                  <TableHead>Fazla Mesai</TableHead>
                  <TableHead>Durum</TableHead>
                  <TableHead className="text-right">İşlem</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.length === 0 && (
                  <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-8">Henüz personel yok</TableCell></TableRow>
                )}
                {list.map((p) => (
                  <TableRow key={p.id} data-testid={`personnel-row-${p.id}`}>
                    <TableCell className="font-medium">{p.ad_soyad}</TableCell>
                    <TableCell>
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground text-xs font-semibold">
                        {PERSONNEL_LABELS[p.personel_turu]}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs">{p.personel_turu === "saglikci_surucu" ? TERCIH_LABELS[p.surucu_tercihi || "yok"] : <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell>{p.fazla_mesai ? <span className="text-xs font-semibold text-amber-700">Evet</span> : <span className="text-xs text-muted-foreground">Hayır</span>}</TableCell>
                    <TableCell>
                      {p.aktif
                        ? <span className="text-xs font-semibold text-green-700">Aktif</span>
                        : <span className="text-xs font-semibold text-muted-foreground">Pasif</span>}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button size="icon" variant="ghost" onClick={() => openEdit(p)} data-testid={`edit-personnel-${p.id}`}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button size="icon" variant="ghost" onClick={() => remove(p.id)} data-testid={`delete-personnel-${p.id}`}>
                        <Trash2 className="w-4 h-4 text-red-600" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="personnel-dialog">
          <DialogHeader>
            <DialogTitle>{editingId ? "Personel Düzenle" : "Yeni Personel"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Ad Soyad</Label>
              <Input value={form.ad_soyad} onChange={(e) => setForm({ ...form, ad_soyad: e.target.value })} data-testid="input-ad-soyad" />
            </div>
            <div>
              <Label>Personel Türü</Label>
              <Select value={form.personel_turu} onValueChange={(v) => setForm({ ...form, personel_turu: v })}>
                <SelectTrigger data-testid="select-personel-turu"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="saglikci">Sağlıkçı</SelectItem>
                  <SelectItem value="surucu">Sürücü</SelectItem>
                  <SelectItem value="saglikci_surucu">Sağlıkçı + Sürücü</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.personel_turu === "saglikci_surucu" && (
              <div>
                <Label>Sürücü Nöbet Tercihi</Label>
                <Select value={form.surucu_tercihi} onValueChange={(v) => setForm({ ...form, surucu_tercihi: v })}>
                  <SelectTrigger data-testid="select-surucu-tercihi"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="12">12 saat sürücü istiyorum</SelectItem>
                    <SelectItem value="24">24 saat sürücü istiyorum</SelectItem>
                    <SelectItem value="yok">Tercihim yok</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground mt-1">24s sürücü nöbetinde ayrıca 12s sürücü atanmaz (2 sağlıkçı + 1×24s sürücü).</p>
              </div>
            )}
            <div className="flex items-center justify-between">
              <div>
                <Label>Fazla Mesai Yapabilir</Label>
                <p className="text-xs text-muted-foreground">Normal hedefin üzerinde görev alabilir</p>
              </div>
              <Switch checked={form.fazla_mesai} onCheckedChange={(v) => setForm({ ...form, fazla_mesai: v })} data-testid="switch-fazla-mesai" />
            </div>
            <div>
              <Label>Açıklama</Label>
              <Input value={form.aciklama} onChange={(e) => setForm({ ...form, aciklama: e.target.value })} />
            </div>
            <div className="flex items-center justify-between">
              <Label>Aktif</Label>
              <Switch checked={form.aktif} onCheckedChange={(v) => setForm({ ...form, aktif: v })} data-testid="switch-aktif" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>İptal</Button>
            <Button onClick={save} data-testid="save-personnel-btn">Kaydet</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
