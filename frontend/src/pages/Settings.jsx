import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTheme } from "@/lib/theme";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Palette, Database, SlidersHorizontal } from "lucide-react";
import { TemplatesCard } from "@/components/TemplatesCard";
import { HolidaysCard } from "@/components/HolidaysCard";
import { DriverTargetsCard } from "@/components/DriverTargetsCard";

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const { isAdmin } = useAuth();
  const [schedulerGap, setSchedulerGap] = useState(4);
  const [savingGap, setSavingGap] = useState(false);

  const loadSchedulerSettings = async () => {
    try {
      const r = await api.get("/scheduler-settings");
      setSchedulerGap(Number(r.data.saglikci_max_nobet_araligi || 4));
    } catch (e) {
      toast.error("Nöbet aralığı ayarı okunamadı: " + (e.response?.data?.detail || e.message));
    }
  };

  useEffect(() => {
    loadSchedulerSettings();
  }, []);

  const saveSchedulerGap = async () => {
    const value = Number(schedulerGap);
    if (!Number.isFinite(value) || value < 1) {
      toast.error("Sağlıkçı maksimum nöbet aralığı en az 1 olmalıdır");
      return;
    }
    setSavingGap(true);
    try {
      const r = await api.patch("/scheduler-settings", { saglikci_max_nobet_araligi: value });
      setSchedulerGap(Number(r.data.saglikci_max_nobet_araligi || value));
      toast.success("Sağlıkçı maksimum nöbet aralığı güncellendi");
    } catch (e) {
      toast.error("Kaydedilemedi: " + (e.response?.data?.detail || e.message));
    } finally {
      setSavingGap(false);
    }
  };

  const seedDemo = async () => {
    try {
      const r = await api.post("/seed/demo");
      if (r.data.seeded) toast.success("Demo personel eklendi");
      else toast.info(`Zaten ${r.data.existing} personel mevcut`);
    } catch (e) { toast.error("Hata: " + e.message); }
  };

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Ayarlar</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight mt-1">Uygulama Ayarları</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-heading"><Palette className="w-5 h-5" /> Tema</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">İki tema arasında geçiş yapabilirsiniz. Tercih tarayıcınıza kaydedilir.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              onClick={() => setTheme("light")}
              data-testid="theme-light-btn"
              className={`text-left rounded-lg border p-4 transition-colors duration-200 ${theme === "light" ? "border-primary ring-2 ring-primary/30 bg-secondary" : "border-border hover:bg-secondary"}`}
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-md" style={{ background: "hsl(222 47% 11%)" }} />
                <div>
                  <div className="font-semibold">Modern Tema</div>
                  <div className="text-xs text-muted-foreground">Beyaz + Lacivert</div>
                </div>
              </div>
            </button>
            <button
              onClick={() => setTheme("emergency")}
              data-testid="theme-emergency-btn"
              className={`text-left rounded-lg border p-4 transition-colors duration-200 ${theme === "emergency" ? "border-primary ring-2 ring-primary/30 bg-secondary" : "border-border hover:bg-secondary"}`}
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-md" style={{ background: "hsl(346 87% 43%)" }} />
                <div>
                  <div className="font-semibold">Acil Teması</div>
                  <div className="text-xs text-muted-foreground">Sağlık / Acil Kırmızı</div>
                </div>
              </div>
            </button>
          </div>
        </CardContent>
      </Card>

      <Card data-testid="scheduler-settings-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-heading"><SlidersHorizontal className="w-5 h-5" /> Nöbet Algoritma Ayarları</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-[280px_1fr] gap-3 items-end">
            <div>
              <Label htmlFor="saglikci-max-gap">Sağlıkçı maksimum nöbet aralığı (gün)</Label>
              <Input
                id="saglikci-max-gap"
                type="number"
                min={1}
                value={schedulerGap}
                onChange={(e) => setSchedulerGap(e.target.value)}
                data-testid="saglikci-max-gap-input"
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={saveSchedulerGap} disabled={!isAdmin || savingGap} data-testid="saglikci-max-gap-save-btn">
                {savingGap ? "Kaydediliyor..." : "Kaydet"}
              </Button>
              {!isAdmin && <span className="text-xs text-muted-foreground self-center">Bu ayarı sadece admin değiştirebilir.</span>}
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Bu ayar yalnızca <strong>Sağlıkçı</strong> ve <strong>Sağlıkçı + Sürücü</strong> personellere uygulanır.
            Sadece <strong>Sürücü</strong> rolündekilere uygulanmaz.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-heading"><Database className="w-5 h-5" /> Veri</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-3">Test için demo personel yüklenebilir (yalnızca personel listesi boş ise).</p>
          <Button onClick={seedDemo} variant="outline" data-testid="settings-seed-btn">Demo Personel Yükle</Button>
        </CardContent>
      </Card>

      <DriverTargetsCard />
      <TemplatesCard />
      <HolidaysCard />

    </div>
  );
}
