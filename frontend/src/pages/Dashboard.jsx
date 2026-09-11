import { useEffect, useState } from "react";
import { api, PERSONNEL_LABELS, MONTHS_TR } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Users, Stethoscope, Car, UserCog, CalendarClock, ListChecks, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

export default function Dashboard() {
  const [personnel, setPersonnel] = useState([]);
  const [yil, setYil] = useState(new Date().getFullYear());
  const [ay, setAy] = useState(new Date().getMonth() + 1);
  const [scheduleStatus, setScheduleStatus] = useState(null);

  const load = async () => {
    const p = await api.get("/personnel");
    setPersonnel(p.data);
    const s = await api.get(`/schedule/${yil}/${ay}`);
    setScheduleStatus(s.data);
  };

  useEffect(() => { load(); }, [yil, ay]);

  const counts = personnel.reduce((acc, p) => {
    if (!p.aktif) return acc;
    acc.total += 1;
    acc[p.personel_turu] = (acc[p.personel_turu] || 0) + 1;
    return acc;
  }, { total: 0 });

  const seedDemo = async () => {
    try {
      const res = await api.post("/seed/demo");
      if (res.data.seeded) toast.success("Demo personel eklendi");
      else toast.info("Zaten personel mevcut");
      load();
    } catch (e) { toast.error("Hata: " + e.message); }
  };

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">112 Acil</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight mt-1">Yönetici Paneli</h1>
          <p className="text-muted-foreground mt-1">Personel, izinler ve otomatik nöbet planlaması</p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <div className="text-xs font-semibold text-muted-foreground mb-1">Yıl</div>
            <Select value={String(yil)} onValueChange={(v) => setYil(Number(v))}>
              <SelectTrigger className="w-24" data-testid="year-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {[2024,2025,2026,2027].map(y=><SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="text-xs font-semibold text-muted-foreground mb-1">Ay</div>
            <Select value={String(ay)} onValueChange={(v) => setAy(Number(v))}>
              <SelectTrigger className="w-36" data-testid="month-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {MONTHS_TR.map((m,i)=><SelectItem key={i} value={String(i+1)}>{m}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Users} label="Toplam Personel" value={counts.total} testid="stat-total" />
        <StatCard icon={Stethoscope} label="Sağlıkçı" value={counts.saglikci || 0} testid="stat-saglikci" />
        <StatCard icon={Car} label="Sürücü" value={counts.surucu || 0} testid="stat-surucu" />
        <StatCard icon={UserCog} label="Sağlıkçı + Sürücü" value={counts.saglikci_surucu || 0} testid="stat-hybrid" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-heading">
              <CalendarClock className="w-5 h-5" /> {MONTHS_TR[ay-1]} {yil} - Nöbet Listesi
            </CardTitle>
          </CardHeader>
          <CardContent>
            {scheduleStatus?.exists ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-100 text-green-800 text-xs font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-600"></span> Oluşturuldu
                  </span>
                  <span className="text-sm text-muted-foreground">{scheduleStatus.gunler?.length || 0} gün planlandı</span>
                </div>
                {scheduleStatus.ihlaller?.length > 0 && (
                  <div className="text-sm text-orange-700">
                    {scheduleStatus.ihlaller.length} uyarı mevcut
                  </div>
                )}
                <div className="flex gap-2 pt-2">
                  <Link to="/nobet"><Button data-testid="open-schedule-btn">Listeyi Aç</Button></Link>
                  <Link to="/istatistikler"><Button variant="outline">İstatistikler</Button></Link>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="text-sm text-muted-foreground">Bu ay için henüz nöbet listesi oluşturulmadı.</div>
                <Link to="/nobet"><Button data-testid="create-schedule-cta">Nöbet Listesi Oluştur</Button></Link>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-heading"><Sparkles className="w-5 h-5" /> Hızlı Eylemler</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Link to="/personeller" className="block"><Button variant="outline" className="w-full justify-start"><Users className="w-4 h-4 mr-2" />Personel Yönetimi</Button></Link>
            <Link to="/izinler" className="block"><Button variant="outline" className="w-full justify-start"><CalendarClock className="w-4 h-4 mr-2" />İzinler / İstekler</Button></Link>
            <Link to="/nobet" className="block"><Button variant="outline" className="w-full justify-start"><ListChecks className="w-4 h-4 mr-2" />Nöbet Listesi</Button></Link>
            {personnel.length === 0 && (
              <Button className="w-full" onClick={seedDemo} data-testid="seed-demo-btn">Demo Personel Yükle</Button>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, testid }) {
  return (
    <Card data-testid={testid} className="hover:-translate-y-[1px] transition-transform duration-200">
      <CardContent className="p-5 flex items-center gap-4">
        <div className="w-11 h-11 rounded-md bg-secondary grid place-items-center text-primary">
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground">{label}</div>
          <div className="text-2xl font-heading font-extrabold mt-0.5">{value}</div>
        </div>
      </CardContent>
    </Card>
  );
}
