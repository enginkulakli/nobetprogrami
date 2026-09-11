"""Türkiye resmi tatilleri (tam gün)."""
from typing import Dict, List

FIXED = [
    ("01-01", "Yılbaşı"),
    ("04-23", "Ulusal Egemenlik ve Çocuk Bayramı"),
    ("05-01", "Emek ve Dayanışma Günü"),
    ("05-19", "Atatürk'ü Anma, Gençlik ve Spor Bayramı"),
    ("07-15", "Demokrasi ve Milli Birlik Günü"),
    ("08-30", "Zafer Bayramı"),
    ("10-29", "Cumhuriyet Bayramı"),
]

RELIGIOUS: Dict[int, List[tuple]] = {
    2024: [("04-10", "Ramazan Bayramı 1. Gün"), ("04-11", "Ramazan Bayramı 2. Gün"), ("04-12", "Ramazan Bayramı 3. Gün"),
           ("06-16", "Kurban Bayramı 1. Gün"), ("06-17", "Kurban Bayramı 2. Gün"), ("06-18", "Kurban Bayramı 3. Gün"), ("06-19", "Kurban Bayramı 4. Gün")],
    2025: [("03-30", "Ramazan Bayramı 1. Gün"), ("03-31", "Ramazan Bayramı 2. Gün"), ("04-01", "Ramazan Bayramı 3. Gün"),
           ("06-06", "Kurban Bayramı 1. Gün"), ("06-07", "Kurban Bayramı 2. Gün"), ("06-08", "Kurban Bayramı 3. Gün"), ("06-09", "Kurban Bayramı 4. Gün")],
    2026: [("03-20", "Ramazan Bayramı 1. Gün"), ("03-21", "Ramazan Bayramı 2. Gün"), ("03-22", "Ramazan Bayramı 3. Gün"),
           ("05-27", "Kurban Bayramı 1. Gün"), ("05-28", "Kurban Bayramı 2. Gün"), ("05-29", "Kurban Bayramı 3. Gün"), ("05-30", "Kurban Bayramı 4. Gün")],
    2027: [("03-09", "Ramazan Bayramı 1. Gün"), ("03-10", "Ramazan Bayramı 2. Gün"), ("03-11", "Ramazan Bayramı 3. Gün"),
           ("05-16", "Kurban Bayramı 1. Gün"), ("05-17", "Kurban Bayramı 2. Gün"), ("05-18", "Kurban Bayramı 3. Gün"), ("05-19", "Kurban Bayramı 4. Gün")],
}


def official_holidays(yil: int) -> List[dict]:
    out = [{"tarih": f"{yil}-{md}", "ad": ad, "kaynak": "resmi"} for md, ad in FIXED]
    out += [{"tarih": f"{yil}-{md}", "ad": ad, "kaynak": "resmi"} for md, ad in RELIGIOUS.get(yil, [])]
    return sorted(out, key=lambda h: h["tarih"])
