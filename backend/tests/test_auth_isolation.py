"""Auth + station isolation tests for 112 Nöbet Listesi."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://shift-emergency.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"kullanici_adi": ADMIN_USER, "sifre": ADMIN_PASS})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and data["user"]["role"] == "admin"
    return data["token"]


@pytest.fixture(scope="module")
def stations(admin_token):
    """Create/find two stations A and B."""
    h = {"Authorization": f"Bearer {admin_token}"}
    suffix = str(int(time.time()))
    names = [f"TEST_A_{suffix}", f"TEST_B_{suffix}"]
    ids = {}
    for n in names:
        r = requests.post(f"{API}/stations", json={"ad": n}, headers=h)
        assert r.status_code == 200, r.text
        ids[n] = r.json()["id"]
    yield {"A": ids[names[0]], "B": ids[names[1]], "names": names}
    # teardown: delete personnel & users & stations
    for sid in ids.values():
        # delete users referencing station
        rs = requests.get(f"{API}/users", headers=h)
        if rs.status_code == 200:
            for u in rs.json():
                if u.get("istasyon_id") == sid and u["kullanici_adi"].startswith("TEST_"):
                    requests.delete(f"{API}/users/{u['id']}", headers=h)
        # delete personnel of station
        hs = {**h, "X-Istasyon-Id": sid}
        rp = requests.get(f"{API}/personnel", headers=hs)
        if rp.status_code == 200:
            for p in rp.json():
                requests.delete(f"{API}/personnel/{p['id']}", headers=hs)
        requests.delete(f"{API}/stations/{sid}", headers=h)


@pytest.fixture(scope="module")
def managers(admin_token, stations):
    h = {"Authorization": f"Bearer {admin_token}"}
    suffix = str(int(time.time()))
    users = {}
    for key in ("A", "B"):
        name = f"TEST_mgr_{key}_{suffix}"
        r = requests.post(f"{API}/users",
                          json={"kullanici_adi": name, "sifre": "pass1234", "istasyon_id": stations[key]},
                          headers=h)
        assert r.status_code == 200, r.text
        # login
        rl = requests.post(f"{API}/auth/login", json={"kullanici_adi": name, "sifre": "pass1234"})
        assert rl.status_code == 200
        users[key] = {"name": name, "token": rl.json()["token"], "user": rl.json()["user"]}
    return users


# ---------- auth tests ----------
class TestAuth:
    def test_admin_login(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"kullanici_adi": ADMIN_USER, "sifre": "nope"})
        assert r.status_code == 401

    def test_no_auth_returns_401(self):
        r = requests.get(f"{API}/personnel")
        assert r.status_code == 401

    def test_auth_me(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_admin_missing_station_header_400(self, admin_token):
        r = requests.get(f"{API}/personnel", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 400


# ---------- admin CRUD + isolation ----------
class TestStationsAndUsers:
    def test_stations_created(self, stations):
        assert stations["A"] and stations["B"] and stations["A"] != stations["B"]

    def test_managers_created(self, managers):
        assert managers["A"]["user"]["role"] == "istasyon_sorumlusu"
        assert managers["A"]["user"]["istasyon_id"] != managers["B"]["user"]["istasyon_id"]

    def test_manager_cannot_list_users(self, managers):
        r = requests.get(f"{API}/users", headers={"Authorization": f"Bearer {managers['A']['token']}"})
        assert r.status_code == 403

    def test_manager_cannot_create_station(self, managers):
        r = requests.post(f"{API}/stations", json={"ad": "TEST_hack"},
                          headers={"Authorization": f"Bearer {managers['A']['token']}"})
        assert r.status_code == 403


class TestStationIsolation:
    def _add_personnel(self, admin_token, sid, name):
        h = {"Authorization": f"Bearer {admin_token}", "X-Istasyon-Id": sid}
        r = requests.post(f"{API}/personnel",
                          json={"ad_soyad": name, "personel_turu": "saglikci"},
                          headers=h)
        assert r.status_code == 200, r.text
        return r.json()

    def test_isolation_personnel(self, admin_token, stations, managers):
        pa = self._add_personnel(admin_token, stations["A"], "TEST_PersonA")
        pb = self._add_personnel(admin_token, stations["B"], "TEST_PersonB")

        # Manager A should only see A's personnel
        rA = requests.get(f"{API}/personnel", headers={"Authorization": f"Bearer {managers['A']['token']}"})
        assert rA.status_code == 200
        namesA = [p["ad_soyad"] for p in rA.json()]
        assert pa["ad_soyad"] in namesA
        assert pb["ad_soyad"] not in namesA

        # Even with X-Istasyon-Id header for B, should be ignored & still A
        rA2 = requests.get(f"{API}/personnel",
                           headers={"Authorization": f"Bearer {managers['A']['token']}",
                                    "X-Istasyon-Id": stations["B"]})
        assert rA2.status_code == 200
        namesA2 = [p["ad_soyad"] for p in rA2.json()]
        assert pb["ad_soyad"] not in namesA2, "Station isolation broken: manager A saw B's personnel via header override"
        assert pa["ad_soyad"] in namesA2

        # Manager B sees only B
        rB = requests.get(f"{API}/personnel", headers={"Authorization": f"Bearer {managers['B']['token']}"})
        assert rB.status_code == 200
        namesB = [p["ad_soyad"] for p in rB.json()]
        assert pb["ad_soyad"] in namesB
        assert pa["ad_soyad"] not in namesB

    def test_manager_cannot_access_other_station_personnel_direct(self, admin_token, stations, managers):
        # Try to update B's personnel via manager A
        pb = self._add_personnel(admin_token, stations["B"], "TEST_direct_target")
        r = requests.patch(f"{API}/personnel/{pb['id']}",
                           json={"ad_soyad": "HACKED"},
                           headers={"Authorization": f"Bearer {managers['A']['token']}"})
        # Should be 404 (isolation) not 200
        assert r.status_code == 404


class TestChangePassword:
    def test_change_password_flow(self, admin_token, stations):
        h = {"Authorization": f"Bearer {admin_token}"}
        suffix = str(int(time.time()))
        name = f"TEST_pwuser_{suffix}"
        r = requests.post(f"{API}/users",
                          json={"kullanici_adi": name, "sifre": "old12345", "istasyon_id": stations["A"]},
                          headers=h)
        assert r.status_code == 200
        uid = r.json()["id"]

        # login
        rl = requests.post(f"{API}/auth/login", json={"kullanici_adi": name, "sifre": "old12345"})
        assert rl.status_code == 200
        tok = rl.json()["token"]

        # change password
        rc = requests.post(f"{API}/auth/change-password",
                           json={"eski_sifre": "old12345", "yeni_sifre": "new12345"},
                           headers={"Authorization": f"Bearer {tok}"})
        assert rc.status_code == 200

        # old fails
        r1 = requests.post(f"{API}/auth/login", json={"kullanici_adi": name, "sifre": "old12345"})
        assert r1.status_code == 401

        # new works
        r2 = requests.post(f"{API}/auth/login", json={"kullanici_adi": name, "sifre": "new12345"})
        assert r2.status_code == 200

        # cleanup
        requests.delete(f"{API}/users/{uid}", headers=h)


class TestOrphans:
    def test_orphans_endpoint(self, admin_token):
        r = requests.get(f"{API}/admin/orphans", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "personnel" in data and "leaves" in data and "schedules" in data


class TestScheduleGenerationWithinStation:
    def test_generate_schedule_isolated(self, admin_token, stations):
        sid = stations["A"]
        h = {"Authorization": f"Bearer {admin_token}", "X-Istasyon-Id": sid}
        # seed demo
        rs = requests.post(f"{API}/seed/demo", headers=h)
        assert rs.status_code == 200
        # generate
        rg = requests.post(f"{API}/schedule/generate",
                           json={"yil": 2026, "ay": 3, "rastgele_yoksay": True},
                           headers=h)
        assert rg.status_code == 200, rg.text
        data = rg.json()
        assert "schedule" in data
        assert data["schedule"]["istasyon_id"] == sid
