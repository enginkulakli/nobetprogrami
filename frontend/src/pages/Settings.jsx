import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Palette, Database } from "lucide-react";
import { TemplatesCard } from "@/components/TemplatesCard";
import { HolidaysCard } from "@/components/HolidaysCard";
import { DriverTargetsCard } from "@/components/DriverTargetsCard";

export default function Settings() {
  const { theme, setTheme } = useTheme();

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

      <Card>
        <CardHeader><CardTitle className="font-heading">Kurallar</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p><strong className="text-foreground">Kesin (Hard) Kurallar:</strong> Yıllık izin, min 12s sürücü dinlenmesi, sağlıkçı arka arkaya 24s yasağı, sürücü max 3 gün üst üste, rol uyumluluğu, iki 24s arasında en az 1 gün.</p>
          <p><strong className="text-foreground">Tercih (Soft) Kurallar:</strong> Çalışma saati dengesi, nöbet sayısı dengesi, hafta sonu dengesi, resmi tatil dengesi, gündüz/gece dengesi, "Nöbet istemiyorum" tercihleri.</p>
        </CardContent>
      </Card>
    </div>
  );
}
