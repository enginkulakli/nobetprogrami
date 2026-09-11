# 112 Nöbet Listesi - Product Requirements

## Original Problem
Türkçe, modern, mobil uyumlu 112 Acil Sağlık Hizmetleri personel nöbet planlama uygulaması. Aylık nöbet listelerini otomatik oluşturur, yönetir, manuel düzenlenebilir. Sadece takvim değil, bir optimizasyon sistemi.

## Architecture
- Backend: FastAPI + MongoDB (motor). Modüler `scheduler.py` merkezi constraint sistemi (hard/soft ayrımı).
- Frontend: React + Tailwind + Shadcn UI + Sonner + Recharts. Dual switchable theme (Modern Light navy / Emergency Red).
- No auth (single admin mode, per user choice).

## Personas
- **Yönetici (Admin)**: Aylık nöbet listesini planlar, personel yönetir, izin ve tercihleri girer, manuel düzenler.

## Core Requirements (static)
- Personel türleri: Sağlıkçı (24s), Sürücü (12s), Sağlıkçı+Sürücü (24s/12s/24s).
- Normal ekip: 2 Sağlıkçı + 2 Sürücü (12s gündüz + 12s gece). Alternatif: 2 Sağlıkçı + 1×24s sürücü.
- Hard constraints (kesin): yıllık izin, min 12h sürücü dinlenme, sağlıkçı arka arkaya 24s yasağı, sürücü max 3 gün üst üste, rol uyumluluğu, iki 24s arası min 1 gün.
- Soft constraints (tercih): çalışma saati/nöbet/hafta sonu/gündüz-gece dengesi, "nöbet istemiyorum" tercihi.
- Aylık yıl/ay bazlı saklama, manuel düzenleme kural kontrolü ile.
- Excel + PDF dışa aktarım.

## Implemented (2026-02)
- ✅ Personnel CRUD (`/api/personnel`, PATCH/DELETE cascades leaves)
- ✅ Seed demo (10 personel)
- ✅ Leaves bulk set/get (`/api/leaves/bulk`, filtreli GET)
- ✅ Otomatik nöbet algoritması (heuristik, hard+soft scoring) - `scheduler.py`
- ✅ Manuel atama + kural doğrulama (`/api/schedule/manual`)
- ✅ İstatistikler (`/api/schedule/{y}/{m}/stats`)
- ✅ Excel export (openpyxl) + PDF export (reportlab) - landscape A4
- ✅ 6 sayfalık frontend: Ana Sayfa, Personeller, İzinler, Nöbet Listesi, İstatistikler, Ayarlar
- ✅ Dual theme switcher (Modern / Emergency Red) - localStorage
- ✅ Mobil menü + responsive tablolar
- ✅ Print stylesheet
- ✅ Backend testing: 18/18 pass

## Backlog / Next Actions
- P1: Çakışan istek çözümlemesi UI (yönetici hangi isteği görmezden gelecek seçsin)
- P1: Önceki aydan taşan nöbet takibi (ilk günler için)
- P2: Resmi tatil ekranı ve tatil dengesi
- P2: İstasyon/grup bazlı kurallar
- P2: Kullanıcı hesabı (multi-user, sonraki faz)
- P2: Manuel edit sonrası real-time kural badge tablonun içinde
