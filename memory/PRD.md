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

## Implemented (2026-06)
- ✅ Çakışan istek ekranı: generate başarısızsa `conflicts` (sorunlu gün ±1 izin/istekler) döner; ConflictDialog seçili istekleri `ignore_leave_ids` ile yoksayar; `rastgele_yoksay` ile otomatik. Listede `yoksayilan_istekler` saklanır.
- ✅ Resmi tatiller: `holidays.py` (2024-2027 sabit + dini bayramlar) + özel tatil CRUD (`/api/holidays`). Tabloda "Tatil" badge, scheduler'da tatil nöbeti dengesi (soft), stats `tatil` sütunu. Ayarlar > Resmi Tatiller kartı.
- ✅ Ay geçişi: `get_carryover` önceki ay listesinin son 3 gününü otomatik alır; yoksa manuel giriş (`PUT /api/carryover/{y}/{m}`). Scheduler `preload_days` ile ilk günlerde dinlenme/24s kuralları kontrol edilir. Manuel düzenleme de carry-over'ı kullanır.
- ✅ Ekip şablonları: `/api/templates` (personel aktif+hedef saat + ≥2 kez tekrar eden haftanın günü bazlı nöbet istemiyorum tercihleri), `apply` ile yeni aya uygulama. Ayarlar kartı + Nöbet Listesi başlığında hızlı uygulama.
- ✅ Testing: iteration_2 — backend 11/11, frontend tüm akışlar pass
- ✅ İzin takviminde tatil işareti (kırmızı bayrak + tooltip tatil adı), legend
- ✅ Canlı kural rozetleri: `GET /api/schedule/{y}/{m}/violations` (`compute_violations`) → hücrede kırmızı (hard) / amber (soft "nöbet istemiyorum") rozet + tooltip nedeni
- ✅ Personel nöbet kartı: `GET .../personnel/{pid}/card` (WhatsApp metni) + `.../personnel/{pid}/export/pdf`; dialog: WhatsApp (wa.me), Kopyala, PDF
- ✅ Tatil rozetinde tooltip ile tatil adı
- ✅ PDF'lerde Türkçe karakter desteği (LiberationSans, `backend/fonts/`)
- ✅ Testing: iteration_3 — backend 8/8, frontend pass

## Backlog / Next Actions
- P2: İstasyon/grup bazlı kurallar
- P2: Kullanıcı hesabı (multi-user, sonraki faz)
- P2: Manuel edit dialogunda personel yanında "uygun/ihlal" ön kontrolü
- P2: İzinler takviminde tatil günlerinin işaretlenmesi ✅ (tamamlandı)
- P2: Ay geçişi son 3 gün yerine yapılandırılabilir gün sayısı
