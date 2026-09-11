import { useEffect, useState } from "react";
import { api, trDayShort } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Flag, Plus, Trash2 } from "lucide-react";

export function HolidaysCard() {
  const [yil, setYil] = useState(new Date().getFullYear());
  const [list, setList] = useState([]);
  const [tarih, setTarih] = useState("");
  const [ad, setAd] = useState("");

  const load = () => api.get(`/holidays/${yil}`).then((r) => setList(r.data));
  useEffect(() => { load(); }, [yil]);

  const add = async () => {
    if (!tarih || !ad.trim()) return toast.error("Tarih ve ad gerekli");
    try {
      await api.post("/holidays", { tarih, ad });
      toast.success("Özel tatil eklendi");
      setTarih(""); setAd("");
      load();
    } catch (e) { toast.error("Hata: " + (e.response?.data?.detail || e.message)); }
  };

  const remove = async (id) => {
    await api.delete(`/holidays/${id}`);
    load();
  };

  return (
    <Card data-testid="holidays-card">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2 font-heading"><Flag className="w-5 h-5" /> Resmi Tatiller</CardTitle>
        <Select value={String(yil)} onValueChange={(v) => setYil(Number(v))}>
          <SelectTrigger className="w-24 h-8" data-testid="holiday-year"><SelectValue /></SelectTrigger>
          <SelectContent>{[2024, 2025, 2026, 2027].map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}</SelectContent>
        </Select>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">Türkiye resmi tatilleri otomatik işaretlenir; tatil nöbetleri personel arasında eşit dağıtılır. İdari izin gibi özel günler ekleyebilirsiniz.</p>
        <div className="flex flex-col sm:flex-row gap-2">
          <Input type="date" value={tarih} onChange={(e) => setTarih(e.target.value)} className="sm:w-44" data-testid="holiday-date-input" />
          <Input placeholder="Tatil adı" value={ad} onChange={(e) => setAd(e.target.value)} data-testid="holiday-name-input" />
          <Button onClick={add} data-testid="holiday-add-btn"><Plus className="w-4 h-4 mr-1" /> Ekle</Button>
        </div>
        <div className="divide-y divide-border rounded-md border border-border max-h-72 overflow-y-auto">
          {list.map((h) => (
            <div key={h.tarih} className="flex items-center gap-3 px-3 py-2 text-sm" data-testid={`holiday-row-${h.tarih}`}>
              <span className="font-mono text-xs w-28">{h.tarih} <span className="text-muted-foreground">{trDayShort(h.tarih)}</span></span>
              <span className="flex-1">{h.ad}</span>
              <Badge variant="outline" className={h.kaynak === "resmi" ? "bg-red-50 text-red-700 border-red-200" : "bg-sky-50 text-sky-700 border-sky-200"}>
                {h.kaynak === "resmi" ? "Resmi" : "Özel"}
              </Badge>
              {h.kaynak === "ozel" && (
                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => remove(h.id)} data-testid={`holiday-delete-${h.tarih}`}>
                  <Trash2 className="w-4 h-4 text-destructive" />
                </Button>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
