import { useEffect, useState } from "react";
import { api, MONTHS_TR, PERSONNEL_LABELS } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid, Tooltip, Legend } from "recharts";

export default function Statistics() {
  const [yil, setYil] = useState(new Date().getFullYear());
  const [ay, setAy] = useState(new Date().getMonth() + 1);
  const [stats, setStats] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    api.get(`/schedule/${yil}/${ay}/stats`).then((r) => setStats(r.data.stats || []))
      .catch(() => { setStats([]); setError("Bu ay için henüz nöbet listesi yok."); });
  }, [yil, ay]);

  const chartData = stats.map((s) => ({
    name: s.ad_soyad.split(" ")[0],
    Saat: s.toplam_saat,
    Hedef: s.hedef_saat,
    HaftaSonu: s.hafta_sonu,
  }));

  return (
    <div className="space-y-6" data-testid="stats-page">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Analiz</div>
          <h1 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight mt-1">İstatistikler</h1>
        </div>
        <div className="flex items-end gap-2">
          <Select value={String(yil)} onValueChange={(v) => setYil(Number(v))}>
            <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
            <SelectContent>
              {[2024,2025,2026,2027].map(y=><SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={String(ay)} onValueChange={(v) => setAy(Number(v))}>
            <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              {MONTHS_TR.map((m,i)=><SelectItem key={i} value={String(i+1)}>{m}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {error && <Card><CardContent className="p-8 text-center text-muted-foreground">{error}</CardContent></Card>}

      {stats.length > 0 && (
        <>
          <Card>
            <CardHeader><CardTitle className="font-heading">Çalışma Saati vs Hedef</CardTitle></CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
                  <Legend />
                  <Bar dataKey="Saat" fill="hsl(var(--primary))" radius={[4,4,0,0]} />
                  <Bar dataKey="Hedef" fill="hsl(var(--muted-foreground))" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="font-heading">Detaylı Tablo</CardTitle></CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Personel</TableHead>
                      <TableHead>Tür</TableHead>
                      <TableHead className="text-right">Nöbet</TableHead>
                      <TableHead className="text-right">Saat</TableHead>
                      <TableHead className="text-right">Hedef</TableHead>
                      <TableHead className="text-right">Fark</TableHead>
                      <TableHead className="text-right">Cts</TableHead>
                      <TableHead className="text-right">Paz</TableHead>
                      <TableHead className="text-right">H.Sonu</TableHead>
                      <TableHead className="text-right">Gündüz</TableHead>
                      <TableHead className="text-right">Gece</TableHead>
                      <TableHead className="text-right">24s Sür.</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {stats.map((s) => (
                      <TableRow key={s.personel_id} data-testid={`stats-row-${s.personel_id}`}>
                        <TableCell className="font-medium">{s.ad_soyad}</TableCell>
                        <TableCell className="text-xs">{PERSONNEL_LABELS[s.personel_turu]}</TableCell>
                        <TableCell className="text-right font-mono">{s.toplam_nobet}</TableCell>
                        <TableCell className="text-right font-mono">{s.toplam_saat}</TableCell>
                        <TableCell className="text-right font-mono text-muted-foreground">{s.hedef_saat}</TableCell>
                        <TableCell className={`text-right font-mono font-semibold ${s.fark < 0 ? "text-orange-600" : s.fark > 0 ? "text-blue-600" : "text-green-600"}`}>
                          {s.fark > 0 ? "+" : ""}{s.fark}
                        </TableCell>
                        <TableCell className="text-right font-mono">{s.cumartesi}</TableCell>
                        <TableCell className="text-right font-mono">{s.pazar}</TableCell>
                        <TableCell className="text-right font-mono font-semibold">{s.hafta_sonu}</TableCell>
                        <TableCell className="text-right font-mono">{s.gunduz}</TableCell>
                        <TableCell className="text-right font-mono">{s.gece}</TableCell>
                        <TableCell className="text-right font-mono">{s.surucu_24}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
