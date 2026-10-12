import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const TOKEN_KEY = "nobet-token";
export const STATION_KEY = "nobet-istasyon";

function getAuthStorage() {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

const AUTH_STORAGE = getAuthStorage();

export function readAuthValue(key) {
  return AUTH_STORAGE?.getItem(key) || "";
}

export function writeAuthValue(key, value) {
  if (!AUTH_STORAGE) return;
  AUTH_STORAGE.setItem(key, value);
}

export function removeAuthValue(key) {
  AUTH_STORAGE?.removeItem(key);
}

// Eski sürümlerde token/istasyon bilgisi kalıcı olarak localStorage'da tutuluyordu.
// Bu yardımcı yalnızca o eski kalıcı kayıtları temizler; aktif oturumu (sessionStorage) TUTAR.
export function clearLegacyAuthStorage() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(STATION_KEY);
  } catch {
    // no-op
  }
}

// Aktif oturumu tamamen kapatır (çıkış / 401). Hem sessionStorage hem de
// eski localStorage kayıtlarını temizler.
export function clearAuthStorage() {
  removeAuthValue(TOKEN_KEY);
  removeAuthValue(STATION_KEY);
  clearLegacyAuthStorage();
}

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = readAuthValue(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const st = readAuthValue(STATION_KEY);
  if (st) config.headers["X-Istasyon-Id"] = st;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const url = err.config?.url || "";
    if (err.response?.status === 401 && !url.includes("/auth/login")) {
      clearAuthStorage();
      if (window.location.pathname !== "/login") window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export function formatApiError(e) {  const detail = e.response?.data?.detail;
  if (detail == null) return e.message || "Bir hata oluştu";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((x) => (x && typeof x.msg === "string" ? x.msg : JSON.stringify(x))).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export async function downloadFile(path, filename) {
  const res = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const PERSONNEL_LABELS = {
  paramedik: "Paramedik",
  att: "ATT",
  surucu: "Sürücü",
  saglikci: "Eski sağlıkçı türü (düzenle)",
  saglikci_surucu: "Eski karma tür (düzenle)",
};

export const TASK_LABELS = {
  saglikci_24: "24s Sağlık Nöbeti",
  surucu_gunduz: "Sürücü 09-21",
  surucu_gece: "Sürücü 21-09",
  surucu_24: "24s Sürücü",
};

export const MONTHS_TR = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

export const DAYS_TR = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cts", "Paz"];

export function trDayShort(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  return DAYS_TR[(d.getDay() + 6) % 7];
}
