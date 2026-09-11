import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const TOKEN_KEY = "nobet-token";
export const STATION_KEY = "nobet-istasyon";

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const st = localStorage.getItem(STATION_KEY);
  if (st) config.headers["X-Istasyon-Id"] = st;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const url = err.config?.url || "";
    if (err.response?.status === 401 && !url.includes("/auth/login")) {
      localStorage.removeItem(TOKEN_KEY);
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
  saglikci: "Sağlıkçı",
  surucu: "Sürücü",
  saglikci_surucu: "Sağlıkçı + Sürücü",
};

export const TASK_LABELS = {
  saglikci_24: "Sağlıkçı 24s",
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
