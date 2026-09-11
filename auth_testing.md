# Auth & Station Isolation — Testing Notes

App: 112 Nöbet Listesi (Turkish). JWT Bearer auth (localStorage `nobet-token`).

## Roles
- admin: sees all stations, manages users & stations. Selects a station via top-bar dropdown (sends header `X-Istasyon-Id`).
- istasyon_sorumlusu: fixed to own station.

## Credentials
- Admin: kullanici_adi=`admin`, sifre=`admin123`.
- Station managers are created by admin under /kullanicilar.

## Key data-testids
- Login: login-username, login-password, login-submit, login-error
- Top bar: station-select-trigger, station-opt-<id>, user-menu-trigger, menu-change-password, menu-logout
- Users page: new-station-btn, station-name-input, save-station-btn, new-user-btn, user-name-input, user-password-input, user-station-select, save-user-btn, assign-orphans-btn
- Change password: old-password-input, new-password-input, save-password-btn

## Isolation contract (backend)
- All data endpoints (/api/personnel, /api/leaves, /api/schedule/*, /api/templates, /api/carryover, /api/stats, exports) require Authorization + station scope.
- Manager scope = own istasyon_id (header ignored). Admin scope = X-Istasyon-Id header (400 if missing).
- Cross-station access (e.g. GET personnel of another station) must return empty / 404, never other station's data.
