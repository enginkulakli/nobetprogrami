import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, TOKEN_KEY, STATION_KEY, formatApiError } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stations, setStations] = useState([]);
  const [stationId, setStationIdState] = useState(() => localStorage.getItem(STATION_KEY) || "");

  const isAdmin = user?.role === "admin";

  const refreshStations = useCallback(async () => {
    try {
      const r = await api.get("/stations");
      setStations(r.data);
      return r.data;
    } catch {
      return [];
    }
  }, []);

  const applyUser = useCallback(async (u) => {
    setUser(u);
    if (u.role === "istasyon_sorumlusu" && u.istasyon_id) {
      localStorage.setItem(STATION_KEY, u.istasyon_id);
      setStationIdState(u.istasyon_id);
    } else if (u.role === "admin") {
      await refreshStations();
    }
  }, [refreshStations]);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) { setLoading(false); return; }
    api.get("/auth/me")
      .then((r) => applyUser(r.data))
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false));
  }, [applyUser]);

  const login = async (kullanici_adi, sifre) => {
    const r = await api.post("/auth/login", { kullanici_adi, sifre });
    localStorage.setItem(TOKEN_KEY, r.data.token);
    await applyUser(r.data.user);
    return r.data.user;
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(STATION_KEY);
    setUser(null);
    setStationIdState("");
    window.location.href = "/login";
  };

  const setStationId = (id) => {
    if (id) localStorage.setItem(STATION_KEY, id);
    else localStorage.removeItem(STATION_KEY);
    setStationIdState(id);
  };

  const changePassword = async (eski_sifre, yeni_sifre) => {
    await api.post("/auth/change-password", { eski_sifre, yeni_sifre });
    setUser((u) => ({ ...u, sifre_degistirildi: true }));
  };

  const stationName = isAdmin
    ? (stations.find((s) => s.id === stationId)?.ad || "")
    : (user?.istasyon_ad || "");

  return (
    <AuthContext.Provider
      value={{ user, loading, isAdmin, stations, stationId, stationName,
        setStationId, refreshStations, login, logout, changePassword, formatApiError }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
