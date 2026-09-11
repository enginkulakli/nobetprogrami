import { NavLink, useLocation } from "react-router-dom";
import { LayoutDashboard, Users, CalendarDays, ListChecks, BarChart3, Settings, Activity, Shield, Building2, LogOut, KeyRound, ChevronDown } from "lucide-react";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator, DropdownMenuLabel } from "@/components/ui/dropdown-menu";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { toast } from "sonner";

const baseLinks = [
  { to: "/", label: "Ana Sayfa", icon: LayoutDashboard, testid: "nav-home" },
  { to: "/personeller", label: "Personeller", icon: Users, testid: "nav-personnel" },
  { to: "/izinler", label: "İzinler / İstekler", icon: CalendarDays, testid: "nav-leaves" },
  { to: "/nobet", label: "Nöbet Listesi", icon: ListChecks, testid: "nav-schedule" },
  { to: "/istatistikler", label: "İstatistikler", icon: BarChart3, testid: "nav-stats" },
  { to: "/ayarlar", label: "Ayarlar", icon: Settings, testid: "nav-settings" },
];

function ChangePasswordDialog({ open, onOpenChange }) {
  const { changePassword, formatApiError } = useAuth();
  const [eski, setEski] = useState("");
  const [yeni, setYeni] = useState("");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!eski || !yeni) { toast.error("Tüm alanları doldurun"); return; }
    setBusy(true);
    try {
      await changePassword(eski, yeni);
      toast.success("Şifreniz güncellendi");
      setEski(""); setYeni(""); onOpenChange(false);
    } catch (e) { toast.error(formatApiError(e)); }
    setBusy(false);
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="change-password-dialog">
        <DialogHeader><DialogTitle>Şifre Değiştir</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div><Label>Mevcut Şifre</Label><Input type="password" value={eski} onChange={(e) => setEski(e.target.value)} data-testid="old-password-input" className="mt-1" /></div>
          <div><Label>Yeni Şifre</Label><Input type="password" value={yeni} onChange={(e) => setYeni(e.target.value)} data-testid="new-password-input" className="mt-1" /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>İptal</Button>
          <Button onClick={save} disabled={busy} data-testid="save-password-btn">Kaydet</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function Layout({ children }) {
  const { theme, setTheme } = useTheme();
  const { user, isAdmin, stations, stationId, stationName, setStationId, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const location = useLocation();

  const links = isAdmin
    ? [...baseLinks, { to: "/kullanicilar", label: "Kullanıcılar", icon: Shield, testid: "nav-users" }]
    : baseLinks;

  const needStation = isAdmin && !stationId && location.pathname !== "/kullanicilar";

  const NavItems = ({ mobile }) => links.map(({ to, label, icon: Icon, testid }) => (
    <NavLink
      key={to} to={to} end={to === "/"}
      data-testid={mobile ? `m-${testid}` : testid}
      onClick={mobile ? () => setOpen(false) : undefined}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 ${mobile ? "py-3" : "py-2.5"} rounded-md text-sm font-medium transition-colors duration-200 ${
          isActive ? "bg-primary text-primary-foreground" : "text-foreground/70 hover:bg-secondary hover:text-foreground"
        }`
      }
    >
      <Icon className="w-4 h-4" /> <span>{label}</span>
    </NavLink>
  ));

  const StationControl = () => {
    if (isAdmin) {
      return (
        <div className="flex items-center gap-2" data-testid="station-selector">
          <Building2 className="w-4 h-4 text-muted-foreground" />
          <Select value={stationId} onValueChange={setStationId}>
            <SelectTrigger className="h-9 w-48" data-testid="station-select-trigger">
              <SelectValue placeholder="İstasyon seçin" />
            </SelectTrigger>
            <SelectContent>
              {stations.length === 0 && <div className="px-3 py-2 text-xs text-muted-foreground">İstasyon yok — önce ekleyin</div>}
              {stations.map((s) => <SelectItem key={s.id} value={s.id} data-testid={`station-opt-${s.id}`}>{s.ad}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      );
    }
    return (
      <div className="flex items-center gap-2 text-sm" data-testid="station-badge">
        <Building2 className="w-4 h-4 text-primary" />
        <span className="font-semibold">{stationName || "İstasyon"}</span>
      </div>
    );
  };

  const UserMenu = () => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2" data-testid="user-menu-trigger">
          <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground grid place-items-center text-xs font-bold">
            {(user?.kullanici_adi || "?").slice(0, 1).toUpperCase()}
          </span>
          <span className="max-w-[120px] truncate">{user?.kullanici_adi}</span>
          <ChevronDown className="w-3.5 h-3.5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52">
        <DropdownMenuLabel>
          <div className="font-semibold">{user?.kullanici_adi}</div>
          <div className="text-xs text-muted-foreground font-normal">{isAdmin ? "Yönetici" : "İstasyon Sorumlusu"}</div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => setPwOpen(true)} data-testid="menu-change-password"><KeyRound className="w-4 h-4 mr-2" /> Şifre Değiştir</DropdownMenuItem>
        <DropdownMenuItem onClick={logout} data-testid="menu-logout" className="text-red-600 focus:text-red-600"><LogOut className="w-4 h-4 mr-2" /> Çıkış Yap</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <div className="min-h-screen bg-background text-foreground flex">
      {/* Sidebar - Desktop */}
      <aside className="hidden md:flex md:w-64 shrink-0 border-r border-border bg-card flex-col no-print">
        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-lg bg-primary text-primary-foreground grid place-items-center">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="font-heading font-extrabold text-lg leading-none">112 Nöbet</div>
              <div className="text-xs text-muted-foreground mt-1">Acil Sağlık Planlaması</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1"><NavItems /></nav>
        <div className="p-3 border-t border-border">
          <Button variant="outline" className="w-full justify-start gap-2" data-testid="theme-toggle-sidebar"
            onClick={() => setTheme(theme === "light" ? "emergency" : "light")}>
            <span className={`w-3 h-3 rounded-full ${theme === "light" ? "bg-primary" : "bg-red-600"}`} />
            {theme === "light" ? "Modern Tema" : "Acil Teması"}
          </Button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        {/* Desktop top bar */}
        <header className="hidden md:flex sticky top-0 z-30 items-center justify-between gap-4 px-6 lg:px-8 py-3 bg-card/80 backdrop-blur border-b border-border no-print">
          <StationControl />
          <UserMenu />
        </header>

        {/* Mobile Header */}
        <header className="md:hidden sticky top-0 z-30 bg-card border-b border-border no-print">
          <div className="flex items-center justify-between p-3">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-lg bg-primary text-primary-foreground grid place-items-center">
                <Activity className="w-4 h-4" />
              </div>
              <div className="font-heading font-bold">112 Nöbet</div>
            </div>
            <div className="flex items-center gap-2">
              <UserMenu />
              <Button variant="ghost" size="icon" onClick={() => setOpen(!open)} data-testid="mobile-menu-toggle">
                {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </Button>
            </div>
          </div>
          <div className="px-3 pb-3"><StationControl /></div>
          {open && (
            <nav className="border-t border-border p-2 space-y-1">
              <NavItems mobile />
              <Button variant="outline" className="w-full mt-2"
                onClick={() => setTheme(theme === "light" ? "emergency" : "light")} data-testid="theme-toggle-mobile">
                {theme === "light" ? "Acil Temasına Geç" : "Modern Temaya Geç"}
              </Button>
            </nav>
          )}
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-full overflow-x-hidden" key={location.pathname + stationId}>
          {needStation ? (
            <div className="max-w-md mx-auto mt-20 text-center space-y-4" data-testid="select-station-prompt">
              <div className="w-14 h-14 rounded-2xl bg-primary/10 text-primary grid place-items-center mx-auto">
                <Building2 className="w-7 h-7" />
              </div>
              <h2 className="font-heading text-2xl font-extrabold">İstasyon Seçin</h2>
              <p className="text-muted-foreground text-sm">
                Yönetici olarak bir istasyonun verilerini görüntülemek için üst menüden bir istasyon seçin.
                {stations.length === 0 && " Henüz istasyon yok — Kullanıcılar sayfasından ekleyebilirsiniz."}
              </p>
              {stations.length === 0 && (
                <NavLink to="/kullanicilar"><Button data-testid="goto-users-btn">Kullanıcılar &amp; İstasyonlar</Button></NavLink>
              )}
            </div>
          ) : children}
        </main>
      </div>

      <ChangePasswordDialog open={pwOpen} onOpenChange={setPwOpen} />
    </div>
  );
}
