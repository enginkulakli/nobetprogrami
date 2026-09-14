import { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  api,
  TOKEN_KEY,
  STATION_KEY,
  formatApiError,
  readAuthValue,
  writeAuthValue,
  removeAuthValue,
  clearAuthStorage,
  clearLegacyAuthStorage,
} from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stations, setStations] = useState([]);
  const [stationId, setStationIdState] = useState(() => readAuthValue(STATION_KEY) || "");

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
      writeAuthValue(STATION_KEY, u.istasyon_id);
      setStationIdState(u.istasyon_id);
    } else if (u.role === "admin") {
      await refreshStations();
    }
  }, [refreshStations]);

  useEffect(() => {
    // Oturum bilgisi artık sessionStorage'da tutulur; sekme/pencere kapatılınca
    // tarayıcı bunu otomatik siler, böylece siteden çıkınca oturum kapanır ve
    // tekrar girişte yeniden kimlik doğrulaması gerekir. Burada yalnızca eski
    // sürümlerden kalan KALICI (localStorage) kayıtları temizliyoruz; aktif
    // sessionStorage oturumuna dokunmuyoruz (aksi halde giriş sonrası tam sayfa
    // yönlendirmesinde oturum silinir).
    clearLegacyAuthStorage();

    const token = readAuthValue(TOKEN_KEY);
    if (!token) { setLoading(false); return; }
    api.get("/auth/me")
      .then((r) => applyUser(r.data))
      .catch(() => removeAuthValue(TOKEN_KEY))
      .finally(() => setLoading(false));
  }, [applyUser]);

  const login = async (kullanici_adi, sifre) => {
    const r = await api.post("/auth/login", { kullanici_adi, sifre });
    writeAuthValue(TOKEN_KEY, r.data.token);
    await applyUser(r.data.user);
    return r.data.user;
  };

  const logout = () => {
    clearAuthStorage();
    setUser(null);
    setStationIdState("");
    window.location.href = "/login";
  };

  const setStationId = (id) => {
    if (id) writeAuthValue(STATION_KEY, id);
    else removeAuthValue(STATION_KEY);
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
