import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Activity, Lock, User, Loader2 } from "lucide-react";
import { formatApiError } from "@/lib/api";

export default function Login() {
  const { login } = useAuth();
  const [kullanici_adi, setAd] = useState("");
  const [sifre, setSifre] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(kullanici_adi.trim(), sifre);
      window.location.href = "/";
    } catch (err) {
      setError(formatApiError(err));
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background text-foreground">
      {/* Left brand panel */}
      <div className="hidden lg:flex flex-col justify-between p-12 bg-primary text-primary-foreground relative overflow-hidden">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-primary-foreground/15 grid place-items-center backdrop-blur">
            <Activity className="w-6 h-6" />
          </div>
          <div className="font-heading font-extrabold text-2xl leading-none">112 Nöbet</div>
        </div>
        <div className="space-y-4 max-w-md">
          <h1 className="font-heading text-4xl xl:text-5xl font-extrabold tracking-tight leading-tight">
            Acil Sağlık Nöbet Planlaması
          </h1>
          <p className="text-primary-foreground/80 text-base">
            İstasyonunuzun aylık nöbet listesini otomatik oluşturun, izinleri ve tercihleri yönetin, adil dağıtımı tek ekrandan takip edin.
          </p>
        </div>
        <div className="text-xs text-primary-foreground/60">© 112 Acil Sağlık Hizmetleri</div>
        <div className="absolute -right-24 -bottom-24 w-96 h-96 rounded-full bg-primary-foreground/5" />
        <div className="absolute -right-10 top-20 w-40 h-40 rounded-full bg-primary-foreground/5" />
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm space-y-8" data-testid="login-page">
          <div className="lg:hidden flex items-center gap-2">
            <div className="w-10 h-10 rounded-lg bg-primary text-primary-foreground grid place-items-center">
              <Activity className="w-5 h-5" />
            </div>
            <div className="font-heading font-extrabold text-lg">112 Nöbet</div>
          </div>

          <div>
            <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Giriş</div>
            <h2 className="font-heading text-3xl font-extrabold tracking-tight mt-1">Hesabınıza girin</h2>
            <p className="text-sm text-muted-foreground mt-2">Kullanıcı adı ve şifreniz ile devam edin.</p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <Label htmlFor="kadi">Kullanıcı Adı</Label>
              <div className="relative mt-1">
                <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input id="kadi" className="pl-9" value={kullanici_adi} autoFocus
                  onChange={(e) => setAd(e.target.value)} placeholder="kullanıcı adı" data-testid="login-username" />
              </div>
            </div>
            <div>
              <Label htmlFor="sifre">Şifre</Label>
              <div className="relative mt-1">
                <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input id="sifre" type="password" className="pl-9" value={sifre}
                  onChange={(e) => setSifre(e.target.value)} placeholder="••••••••" data-testid="login-password" />
              </div>
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2" data-testid="login-error">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={busy} data-testid="login-submit">
              {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Giriş Yap
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
