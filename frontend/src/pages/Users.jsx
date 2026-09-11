import { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Building2, Trash2, Pencil, UserPlus, Plus, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

export default function Users() {
  const { refreshStations } = useAuth();
  const [stations, setStations] = useState([]);
  const [users, setUsers] = useState([]);
  const [orphans, setOrphans] = useState(null);

  // station dialog
  const [stOpen, setStOpen] = useState(false);
  const [stEditId, setStEditId] = useState(null);
  const [stAd, setStAd] = useState("");

  // user dialog
  const [uOpen, setUOpen] = useState(false);
  const [uEditId, setUEditId] = useState(null);
  const [uForm, setUForm] = useState({ kullanici_adi: "", sifre: "", istasyon_id: "" });

  // orphan assign
  const [orphanTarget, setOrphanTarget] = useState("");

  const load = async () => {
    const [s, u, o] = await Promise.all([
      api.get("/stations"), api.get("/users"), api.get("/admin/orphans"),
    ]);
    setStations(s.data); setUsers(u.data); setOrphans(o.data);
  };
  useEffect(() => { load(); }, []);

  // ---- stations ----
  const openNewStation = () => { setStEditId(null); setStAd(""); setStOpen(true); };
  const openEditStation = (s) => { setStEditId(s.id); setStAd(s.ad); setStOpen(true); };
  const saveStation = async () => {
    if (!stAd.trim()) { toast.error("İstasyon adı gerekli"); return; }
    try {
      if (stEditId) await api.patch(`/stations/${stEditId}`, { ad: stAd.trim() });
      else await api.post("/stations", { ad: stAd.trim() });
      toast.success("Kaydedildi"); setStOpen(false); await load(); await refreshStations();
    } catch (e) { toast.error(formatApiError(e)); }
  };
  const removeStation = async (s) => {
    if (!window.confirm(`"${s.ad}" istasyonu silinsin mi?`)) return;
    try { await api.delete(`/stations/${s.id}`); toast.success("Silindi"); await load(); await refreshStations(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  // ---- users ----
  const openNewUser = () => { setUEditId(null); setUForm({ kullanici_adi: "", sifre: "", istasyon_id: stations[0]?.id || "" }); setUOpen(true); };
  const openEditUser = (u) => { setUEditId(u.id); setUForm({ kullanici_adi: u.kullanici_adi, sifre: "", istasyon_id: u.istasyon_id || "" }); setUOpen(true); };
  const saveUser = async () => {
    if (!uForm.kullanici_adi.trim()) { toast.error("Kullanıcı adı gerekli"); return; }
    if (!uForm.istasyon_id) { toast.error("İstasyon seçin"); return; }
    if (!uEditId && !uForm.sifre) { toast.error("Şifre gerekli"); return; }
    try {
      if (uEditId) {
        const payload = { kullanici_adi: uForm.kullanici_adi.trim(), istasyon_id: uForm.istasyon_id };
        if (uForm.sifre) payload.sifre = uForm.sifre;
        await api.patch(`/users/${uEditId}`, payload);
      } else {
        await api.post("/users", { kullanici_adi: uForm.kullanici_adi.trim(), sifre: uForm.sifre, istasyon_id: uForm.istasyon_id });
      }
      toast.success("Kaydedildi"); setUOpen(false); load();
    } catch (e) { toast.error(formatApiError(e)); }
  };
  const removeUser = async (u) => {
    if (!window.confirm(`"${u.kullanici_adi}" kullanıcısı silinsin mi?`)) return;
    try { await api.delete(`/users/${u.id}`); toast.success("Silindi"); load(); }
    catch (e) { toast.error(formatApiError(e)); }
  };

  const assignOrphans = async () => {
    if (!orphanTarget) { toast.error("İstasyon seçin"); return; }
    try {
      const r = await api.post("/admin/assign-orphans", { istasyon_id: orphanTarget });
      toast.success(`${r.data.atanan.personnel} personel taşındı`); load();
    } catch (e) { toast.error(formatApiError(e)); }
  };

  const hasOrphans = orphans && (orphans.personnel || orphans.leaves || orphans.schedules);

  return (
    <div className="space-y-6" data-testid="users-page">
      <div>
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Yönetim</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight mt-1">Kullanıcılar &amp; İstasyonlar</h1>
      </div>

      {hasOrphans && (
        <Card className="border-amber-300 bg-amber-50" data-testid="orphans-card">
          <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center gap-3">
            <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0" />
            <div className="flex-1 text-sm text-amber-900">
              Bir istasyona atanmamış veriler var: <b>{orphans.personnel}</b> personel, <b>{orphans.leaves}</b> izin/istek, <b>{orphans.schedules}</b> nöbet listesi. Bir istasyona taşıyın.
            </div>
            <div className="flex gap-2">
              <Select value={orphanTarget} onValueChange={setOrphanTarget}>
                <SelectTrigger className="w-44" data-testid="orphan-station-select"><SelectValue placeholder="İstasyon seç" /></SelectTrigger>
                <SelectContent>{stations.map((s) => <SelectItem key={s.id} value={s.id}>{s.ad}</SelectItem>)}</SelectContent>
              </Select>
              <Button onClick={assignOrphans} data-testid="assign-orphans-btn">Taşı</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stations */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="flex items-center gap-2 font-heading text-base"><Building2 className="w-5 h-5 text-primary" /> İstasyonlar</CardTitle>
          <Button size="sm" onClick={openNewStation} data-testid="new-station-btn"><Plus className="w-4 h-4 mr-1" /> Yeni İstasyon</Button>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader><TableRow><TableHead>İstasyon</TableHead><TableHead>Personel</TableHead><TableHead className="text-right">İşlem</TableHead></TableRow></TableHeader>
              <TableBody>
                {stations.length === 0 && <TableRow><TableCell colSpan={3} className="text-center text-muted-foreground py-8">Henüz istasyon yok</TableCell></TableRow>}
                {stations.map((s) => (
                  <TableRow key={s.id} data-testid={`station-row-${s.id}`}>
                    <TableCell className="font-medium">{s.ad}</TableCell>
                    <TableCell>{s.personel_sayisi ?? 0}</TableCell>
                    <TableCell className="text-right">
                      <Button size="icon" variant="ghost" onClick={() => openEditStation(s)} data-testid={`edit-station-${s.id}`}><Pencil className="w-4 h-4" /></Button>
                      <Button size="icon" variant="ghost" onClick={() => removeStation(s)} data-testid={`delete-station-${s.id}`}><Trash2 className="w-4 h-4 text-red-600" /></Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Users */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="flex items-center gap-2 font-heading text-base"><UserPlus className="w-5 h-5 text-primary" /> İstasyon Sorumluları</CardTitle>
          <Button size="sm" onClick={openNewUser} disabled={stations.length === 0} data-testid="new-user-btn"><Plus className="w-4 h-4 mr-1" /> Yeni Sorumlu</Button>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader><TableRow><TableHead>Kullanıcı Adı</TableHead><TableHead>İstasyon</TableHead><TableHead>Şifre Değiştirildi</TableHead><TableHead className="text-right">İşlem</TableHead></TableRow></TableHeader>
              <TableBody>
                {users.length === 0 && <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground py-8">Henüz sorumlu yok</TableCell></TableRow>}
                {users.map((u) => (
                  <TableRow key={u.id} data-testid={`user-row-${u.id}`}>
                    <TableCell className="font-medium">{u.kullanici_adi}</TableCell>
                    <TableCell>{u.istasyon_ad || <span className="text-red-600 text-xs">Atanmamış</span>}</TableCell>
                    <TableCell>{u.sifre_degistirildi ? <span className="text-xs text-green-700">Evet</span> : <span className="text-xs text-muted-foreground">İlk şifre</span>}</TableCell>
                    <TableCell className="text-right">
                      <Button size="icon" variant="ghost" onClick={() => openEditUser(u)} data-testid={`edit-user-${u.id}`}><Pencil className="w-4 h-4" /></Button>
                      <Button size="icon" variant="ghost" onClick={() => removeUser(u)} data-testid={`delete-user-${u.id}`}><Trash2 className="w-4 h-4 text-red-600" /></Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Station dialog */}
      <Dialog open={stOpen} onOpenChange={setStOpen}>
        <DialogContent data-testid="station-dialog">
          <DialogHeader><DialogTitle>{stEditId ? "İstasyon Düzenle" : "Yeni İstasyon"}</DialogTitle></DialogHeader>
          <div><Label>İstasyon Adı</Label><Input value={stAd} onChange={(e) => setStAd(e.target.value)} data-testid="station-name-input" className="mt-1" /></div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setStOpen(false)}>İptal</Button>
            <Button onClick={saveStation} data-testid="save-station-btn">Kaydet</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* User dialog */}
      <Dialog open={uOpen} onOpenChange={setUOpen}>
        <DialogContent data-testid="user-dialog">
          <DialogHeader><DialogTitle>{uEditId ? "Sorumlu Düzenle" : "Yeni İstasyon Sorumlusu"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div><Label>Kullanıcı Adı</Label><Input value={uForm.kullanici_adi} onChange={(e) => setUForm({ ...uForm, kullanici_adi: e.target.value })} data-testid="user-name-input" className="mt-1" /></div>
            <div>
              <Label>{uEditId ? "Yeni Şifre (boş bırakırsanız değişmez)" : "İlk Şifre"}</Label>
              <Input type="password" value={uForm.sifre} onChange={(e) => setUForm({ ...uForm, sifre: e.target.value })} data-testid="user-password-input" className="mt-1" />
            </div>
            <div>
              <Label>Bağlı İstasyon</Label>
              <Select value={uForm.istasyon_id} onValueChange={(v) => setUForm({ ...uForm, istasyon_id: v })}>
                <SelectTrigger data-testid="user-station-select" className="mt-1"><SelectValue placeholder="İstasyon seç" /></SelectTrigger>
                <SelectContent>{stations.map((s) => <SelectItem key={s.id} value={s.id}>{s.ad}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUOpen(false)}>İptal</Button>
            <Button onClick={saveUser} data-testid="save-user-btn">Kaydet</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
