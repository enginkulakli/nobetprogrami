import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

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
