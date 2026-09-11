import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { ThemeProvider } from "@/lib/theme";
import { AuthProvider, useAuth } from "@/lib/auth";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Personnel from "@/pages/Personnel";
import Leaves from "@/pages/Leaves";
import Schedule from "@/pages/Schedule";
import Statistics from "@/pages/Statistics";
import Settings from "@/pages/Settings";
import Users from "@/pages/Users";
import ForcePassword from "@/pages/ForcePassword";
import { Loader2 } from "lucide-react";

function AdminOnly({ children }) {
  const { isAdmin } = useAuth();
  return isAdmin ? children : <Navigate to="/" replace />;
}

function ProtectedApp() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/personeller" element={<Personnel />} />
        <Route path="/izinler" element={<Leaves />} />
        <Route path="/nobet" element={<Schedule />} />
        <Route path="/istatistikler" element={<Statistics />} />
        <Route path="/ayarlar" element={<Settings />} />
        <Route path="/kullanicilar" element={<AdminOnly><Users /></AdminOnly>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center bg-background text-foreground">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }
  const mustChangePassword = user && user.role === "istasyon_sorumlusu" && !user.sifre_degistirildi;
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/*" element={
        !user ? <Navigate to="/login" replace />
          : mustChangePassword ? <ForcePassword />
          : <ProtectedApp />
      } />
    </Routes>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
          <Toaster position="bottom-right" richColors />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
