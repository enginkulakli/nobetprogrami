import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Car, Save } from "lucide-react";

export function DriverTargetsCard() {
  const [drivers, setDrivers] = useState([]);
  const [draft, setDraft] = useState({});

  const load = () => api.get("/personnel").then((r) => {
    const d = r.data.filter((p) => p.personel_turu === "surucu");
    setDrivers(d);
    setDraft(Object.fromEntries(d.map((p) => [p.id, { h1: p.nobet_hedef_1_15 ?? "", h2: p.nobet_hedef_16_son ?? "" }])));
  });
  useEffect(() => { load(); }, []);

  const setVal = (id, key, v) => setDraft((d) => ({ ...d, [id]: { ...d[id], [key]: v } }));
  const toNum = (v) => (v === "" || v === null ? null : Math.max(0, Number(v)));

  const save = async (p) => {
    const d = draft[p.id];
    try {
      await api.patch(`/personnel/${p.id}`, { nobet_hedef_1_15: toNum(d.h1), nobet_hedef_16_son: toNum(d.h2) });
      toast.success(`${p.ad_soyad} hedefi kaydedildi`);
      load();
    } catch (e) { toast.error("Kaydedilemedi: " + (e.response?.data?.detail || e.message)); }
  };

  const clear = async (p) => {
    await api.patch(`/personnel/${p.id}`, { nobet_hedef_1_15: null, nobet_hedef_16_son: null });
    toast.success("Hedef kaldırıldı");
    load();
  };

  return (
    <Card data-testid="driver-targets-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 font-heading"><Car className="w-5 h-5" /> Sürücü Nöbet Hedefleri</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">Yalnızca <strong>Sürücü</strong> rolündeki personel için: ayın 1–15'i ve 16–ay sonu aralıklarına girdiğiniz değerler <strong>zorunlu minimum</strong> sürücü nöbet sayısıdır. Sistem bu minimumları mutlaka doldurmaya çalışır; boş bırakılan alan için minimum uygulanmaz. Dinlenme ve ardışık nöbet gibi zorunlu kurallar her zaman önceliklidir.</p>
        {drivers.length === 0 ? (
          <div className="text-sm text-muted-foreground p-4 rounded-md bg-secondary text-center" data-testid="driver-targets-empty">Sürücü rolünde personel yok.</div>
        ) : (
          <div className="divide-y divide-border rounded-md border border-border">
            <div className="hidden sm:grid grid-cols-[1fr_120px_120px_140px] gap-2 px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
              <span>Sürücü</span><span>1–15 nöbet</span><span>16–ay sonu</span><span></span>
            </div>
            {drivers.map((p) => {
              const d = draft[p.id] || { h1: "", h2: "" };
              const dirty = String(d.h1) !== String(p.nobet_hedef_1_15 ?? "") || String(d.h2) !== String(p.nobet_hedef_16_son ?? "");
              return (
                <div key={p.id} className="grid grid-cols-1 sm:grid-cols-[1fr_120px_120px_140px] gap-2 items-center px-3 py-2" data-testid={`driver-target-row-${p.id}`}>
                  <div className="text-sm font-semibold">{p.ad_soyad}{!p.aktif && <span className="text-xs text-muted-foreground ml-1">(Pasif)</span>}</div>
                  <Input type="number" min={0} max={15} placeholder="—" value={d.h1} onChange={(e) => setVal(p.id, "h1", e.target.value)} className="h-8" data-testid={`driver-target-h1-${p.id}`} />
                  <Input type="number" min={0} max={16} placeholder="—" value={d.h2} onChange={(e) => setVal(p.id, "h2", e.target.value)} className="h-8" data-testid={`driver-target-h2-${p.id}`} />
                  <div className="flex gap-1">
                    <Button size="sm" variant={dirty ? "default" : "outline"} onClick={() => save(p)} data-testid={`driver-target-save-${p.id}`}><Save className="w-3.5 h-3.5 mr-1" /> Kaydet</Button>
                    {(p.nobet_hedef_1_15 != null || p.nobet_hedef_16_son != null) && (
                      <Button size="sm" variant="ghost" onClick={() => clear(p)} data-testid={`driver-target-clear-${p.id}`}>Kaldır</Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
