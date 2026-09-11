import { NavLink, useLocation } from "react-router-dom";
import { LayoutDashboard, Users, CalendarDays, ListChecks, BarChart3, Settings, Activity } from "lucide-react";
import { useTheme } from "@/lib/theme";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { Menu, X } from "lucide-react";

const links = [
  { to: "/", label: "Ana Sayfa", icon: LayoutDashboard, testid: "nav-home" },
  { to: "/personeller", label: "Personeller", icon: Users, testid: "nav-personnel" },
  { to: "/izinler", label: "İzinler / İstekler", icon: CalendarDays, testid: "nav-leaves" },
  { to: "/nobet", label: "Nöbet Listesi", icon: ListChecks, testid: "nav-schedule" },
  { to: "/istatistikler", label: "İstatistikler", icon: BarChart3, testid: "nav-stats" },
  { to: "/ayarlar", label: "Ayarlar", icon: Settings, testid: "nav-settings" },
];

export default function Layout({ children }) {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const location = useLocation();

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
        <nav className="flex-1 p-3 space-y-1">
          {links.map(({ to, label, icon: Icon, testid }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              data-testid={testid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors duration-200 ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-foreground/70 hover:bg-secondary hover:text-foreground"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-border">
          <Button
            variant="outline"
            className="w-full justify-start gap-2"
            data-testid="theme-toggle-sidebar"
            onClick={() => setTheme(theme === "light" ? "emergency" : "light")}
          >
            <span className={`w-3 h-3 rounded-full ${theme === "light" ? "bg-primary" : "bg-red-600"}`} />
            {theme === "light" ? "Modern Tema" : "Acil Teması"}
          </Button>
        </div>
      </aside>

      {/* Mobile Header */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="md:hidden sticky top-0 z-30 bg-card border-b border-border no-print">
          <div className="flex items-center justify-between p-3">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-lg bg-primary text-primary-foreground grid place-items-center">
                <Activity className="w-4 h-4" />
              </div>
              <div className="font-heading font-bold">112 Nöbet</div>
            </div>
            <Button variant="ghost" size="icon" onClick={() => setOpen(!open)} data-testid="mobile-menu-toggle">
              {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </Button>
          </div>
          {open && (
            <nav className="border-t border-border p-2 space-y-1">
              {links.map(({ to, label, icon: Icon, testid }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  data-testid={`m-${testid}`}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-3 rounded-md text-sm font-medium ${
                      isActive ? "bg-primary text-primary-foreground" : "hover:bg-secondary"
                    }`
                  }
                >
                  <Icon className="w-4 h-4" /> {label}
                </NavLink>
              ))}
              <Button
                variant="outline"
                className="w-full mt-2"
                onClick={() => setTheme(theme === "light" ? "emergency" : "light")}
                data-testid="theme-toggle-mobile"
              >
                {theme === "light" ? "Acil Temasına Geç" : "Modern Temaya Geç"}
              </Button>
            </nav>
          )}
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-full overflow-x-hidden" key={location.pathname}>
          {children}
        </main>
      </div>
    </div>
  );
}
