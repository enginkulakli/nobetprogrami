import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShieldCheck, Lock, Loader2, LogOut } from "lucide-react";
import { formatApiError } from "@/lib/api";

export default function ForcePassword() {
  const { changePassword, logout, user } = useAuth();
  const [eski, setEski] = useState("");
  const [yeni, setYeni] = useState("");
  const [tekrar, setTekrar] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (yeni.length < 4) { setError("Yeni şifre en az 4 karakter olmalı"); return; }
    if (yeni !== tekrar) { setError("Yeni şifreler eşleşmiyor"); return; }
    if (yeni === eski) { setError("Yeni şifre mevcut şifreden farklı olmalı"); return; }
    setBusy(true);
    try {
      await changePassword(eski, yeni);
      window.location.href = "/";
    } catch (err) {
      setError(formatApiError(err));
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center bg-background text-foreground p-6">
      <div className="w-full max-w-md space-y-6" data-testid="force-password-page">
        <div className="text-center space-y-3">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 text-primary grid place-items-center mx-auto">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <h1 className="font-heading text-2xl font-extrabold tracking-tight">Şifrenizi Belirleyin</h1>
          <p className="text-sm text-muted-foreground">
            <b>{user?.kullanici_adi}</b> — güvenliğiniz için ilk girişte size verilen geçici şifreyi değiştirmeniz gerekiyor.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4 bg-card border border-border rounded-xl p-6">
          <div>
            <Label htmlFor="eski">Mevcut (geçici) şifre</Label>
            <div className="relative mt-1">
              <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input id="eski" type="password" className="pl-9" value={eski} autoFocus
                onChange={(e) => setEski(e.target.value)} data-testid="force-old-password" />
            </div>
          </div>
          <div>
            <Label htmlFor="yeni">Yeni şifre</Label>
            <Input id="yeni" type="password" className="mt-1" value={yeni}
              onChange={(e) => setYeni(e.target.value)} data-testid="force-new-password" />
          </div>
          <div>
            <Label htmlFor="tekrar">Yeni şifre (tekrar)</Label>
            <Input id="tekrar" type="password" className="mt-1" value={tekrar}
              onChange={(e) => setTekrar(e.target.value)} data-testid="force-new-password-repeat" />
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2" data-testid="force-error">
              {error}
            </div>
          )}

          <Button type="submit" className="w-full" disabled={busy} data-testid="force-submit">
            {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
            Şifreyi Değiştir ve Devam Et
          </Button>
          <Button type="button" variant="ghost" className="w-full text-muted-foreground" onClick={logout} data-testid="force-logout">
            <LogOut className="w-4 h-4 mr-2" /> Çıkış Yap
          </Button>
        </form>
      </div>
    </div>
  );
}
