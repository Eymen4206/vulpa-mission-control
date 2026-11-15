# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""Canlı ve arşiv hava durumu: Meteomatics (anlık / arşiv) + Open-Meteo (30 günlük anomali, yedek).

app.py içindeki fonksiyonların birebir kopyası; ağ ya da kimlik doğrulama hatasında istisna fırlatmaz,
mevsimsel simülasyona geçer. Dil/arayüz yardımcıları (compass, wlabel, weather_sentence …) app.py'de kalır.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests
import streamlit as st
from requests.auth import HTTPBasicAuth

from .climatology import climatology_anomaly, normal_values, region_normals
from .config import MM_CORE, MM_EXTRA, MM_URL, NOW, OM_ARCHIVE_URL, RETRY_AFTER, WEATHER_TTL, hist_date
from .regions import REGION_LIST

WEATHER_CODES = (
    ((0,), "Açık", "☀️", "🌙"), ((1, 2), "Parçalı bulutlu", "⛅", "☁️"), ((3,), "Kapalı", "☁️", "☁️"),
    ((45, 48), "Sisli", "🌫️", "🌫️"), ((51, 53, 55, 56, 57), "Çisenti", "🌦️", "🌦️"),
    ((61, 63, 65, 66, 67), "Yağmurlu", "🌧️", "🌧️"), ((71, 73, 75, 77), "Karlı", "🌨️", "🌨️"),
    ((80, 81, 82), "Sağanak", "🌧️", "🌧️"), ((85, 86), "Kar sağanağı", "🌨️", "🌨️"),
    ((95, 96, 99), "Gök gürültülü fırtına", "⛈️", "⛈️"),
)


def describe_code(code: int, is_day: bool) -> tuple[str, str]:
    for codes, label, day_icon, night_icon in WEATHER_CODES:
        if code in codes:
            return label, day_icon if is_day else night_icon
    return "Bilinmiyor", "·"



def _fallback_weather(year: int = 0, month: int | None = None, day: int | None = None) -> dict:
    """Ağ yoksa: mevsim ve enlem kuşağına dayalı tutarlı yaklaşık değerler (açıkça 'tahmini' etiketlenir)."""
    when = hist_date(year, month, day) if year else datetime.now(timezone.utc)
    month = when.month
    data = {}
    normals_used = 0
    for r in REGION_LIST:
        normals = region_normals(r.name)
        if normals is not None:   # NASA POWER iklim normali (gerçekçi yedek)
            v = normal_values(normals, r.lon, when)
            data[r.name] = {**v, "wind_dir": 90.0 if abs(r.lat) < 30 else (270.0 if abs(r.lat) < 60 else 90.0),
                            "anomaly": None, "label": "Tahmini", "icon": "≈"}
            normals_used += 1
            continue
        alat = abs(r.lat)
        season = math.cos(2 * math.pi * (month - (7 if r.lat >= 0 else 1)) / 12)
        temp = 27 - 0.42 * alat + 9 * season * min(1.0, alat / 35)
        # Genel dolaşım: tropiklerde alize (doğudan), orta enlemlerde batı rüzgârları, kutuplarda doğudan
        wind_dir = 90.0 if alat < 30 else (270.0 if alat < 60 else 90.0)
        pressure = 1010 + 10 * math.exp(-((alat - 30) / 10) ** 2) - 8 * math.exp(-((alat - 60) / 8) ** 2)
        data[r.name] = {"temp": temp, "humidity": None, "wind": 15.0, "wind_dir": wind_dir, "pressure": pressure,
                        "anomaly": 0.0, "label": "Tahmini", "icon": "≈"}
    stamp = when.strftime("%d.%m.%Y %H:%M") if year else NOW.strftime("%H:%M")
    return {"live": False, "time": stamp, "data": data, "year": year, "month": when.month, "day": when.day,
            "date": when.strftime("%Y-%m-%d"),
            "source": ("Veri kaynağına ulaşılamadı · NASA POWER iklim normali (tahmini)" if normals_used
                       else "Veri kaynağına ulaşılamadı · mevsimsel simülasyon"),
            "provider": "İklim normali" if normals_used else "Simülasyon",
            "anomaly_live": False, "anomaly_kind": None}


# Meteomatics hava sembolleri (gece için +100)
MM_SYMBOLS = {
    1: ("Açık", "☀️", "🌙"), 2: ("Az bulutlu", "🌤️", "☁️"), 3: ("Parçalı bulutlu", "⛅", "☁️"),
    4: ("Kapalı", "☁️", "☁️"), 5: ("Yağmurlu", "🌧️", "🌧️"), 6: ("Karla karışık yağmur", "🌨️", "🌨️"),
    7: ("Karlı", "🌨️", "🌨️"), 8: ("Sağanak", "🌧️", "🌧️"), 9: ("Kar sağanağı", "🌨️", "🌨️"),
    10: ("Sulu kar sağanağı", "🌨️", "🌨️"), 11: ("Hafif sis", "🌫️", "🌫️"), 12: ("Yoğun sis", "🌫️", "🌫️"),
    13: ("Donan yağmur", "🌧️", "🌧️"), 14: ("Gök gürültülü fırtına", "⛈️", "⛈️"), 15: ("Çisenti", "🌦️", "🌦️"),
    16: ("Kum fırtınası", "🌪️", "🌪️"),
}


def describe_symbol(idx: int) -> tuple[str, str] | None:
    night = idx > 100
    entry = MM_SYMBOLS.get(idx - 100 if night else idx)
    return (entry[0], entry[2] if night else entry[1]) if entry else None


def meteomatics_auth() -> HTTPBasicAuth | None:
    """Kimlik bilgileri yalnızca st.secrets['meteomatics'] (veya ortam değişkenleri) üzerinden okunur."""
    try:
        sec = st.secrets["meteomatics"]
        user, password = sec["METEOMATICS_USER"], sec["METEOMATICS_PASS"]
    except Exception:
        user, password = os.environ.get("METEOMATICS_USER", ""), os.environ.get("METEOMATICS_PASS", "")
    return HTTPBasicAuth(user, password) if user and password else None


def mm_time(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def meteomatics_now(params: tuple, locations: str, timeout: float = 15, when: str = "now") -> tuple[dict, str]:
    """Meteomatics tek an sorgusu ('now' ya da ISO tarih → geçmiş veri).
    Dönüş: {parametre: {(enlem, boylam): değer}}, 'SS:DD' (UTC)."""
    auth = meteomatics_auth()
    if auth is None:
        raise RuntimeError("Meteomatics kimlik bilgisi tanımlı değil")
    resp = requests.get(f"{MM_URL}/{when}/{','.join(params)}/{locations}/json", auth=auth, timeout=timeout)
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "OK":
        raise ValueError(body.get("message", "Meteomatics hatası"))
    out, stamp = {}, ""
    for block in body["data"]:
        values = {}
        for c in block["coordinates"]:
            v = c["dates"][0]["value"]
            values[(round(float(c["lat"]), 4), round(float(c["lon"]), 4))] = None if v is None or v <= -999 else float(v)
            stamp = c["dates"][0]["date"][11:16]
        out[block["parameter"]] = values
    return out, stamp


def meteomatics_daily_anomaly(locations: str, day: datetime, timeout: float = 25) -> dict:
    """Seçilen günün 24 saatlik ortalama sıcaklığının önceki 30 günün ortalamasından sapması (°C).
    Meteomatics t_mean_2m_24h:C zaman serisi (P1D adımlı) tek istekte alınır. Dönüş: {(enlem, boylam): sapma}."""
    auth = meteomatics_auth()
    if auth is None:
        raise RuntimeError("Meteomatics kimlik bilgisi tanımlı değil")
    end = day.replace(hour=0, minute=0, second=0) + timedelta(days=1)
    start = end - timedelta(days=30)
    resp = requests.get(f"{MM_URL}/{mm_time(start)}--{mm_time(end)}:P1D/t_mean_2m_24h:C/{locations}/json",
                        auth=auth, timeout=timeout)
    resp.raise_for_status()
    out = {}
    for c in resp.json()["data"][0]["coordinates"]:
        vals = [d["value"] for d in c["dates"] if d["value"] is not None and d["value"] > -999]
        key = (round(float(c["lat"]), 4), round(float(c["lon"]), 4))
        out[key] = vals[-1] - float(np.mean(vals[:-1])) if len(vals) >= 8 else None
    return out


def _open_meteo_cities() -> tuple[dict, str]:
    """Open-Meteo: anlık değerler (yedek) ve son 30 günün günlük ortalamasından termal anomali."""
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": ",".join(f"{r.lat:.4f}" for r in REGION_LIST),
            "longitude": ",".join(f"{r.lon:.4f}" for r in REGION_LIST),
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,"
                       "wind_direction_10m,pressure_msl,is_day",
            "daily": "temperature_2m_mean",
            "past_days": 30,
            "forecast_days": 1,
            "timezone": "UTC",
        },
        timeout=10,
    )
    resp.raise_for_status()
    payload = resp.json()
    payload = payload if isinstance(payload, list) else [payload]
    if len(payload) != len(REGION_LIST):
        raise ValueError("eksik yanıt")
    data = {}
    for region, item in zip(REGION_LIST, payload):
        cur = item["current"]
        label, icon = describe_code(int(cur["weather_code"]), bool(cur.get("is_day", 1)))
        means = [v for v in item.get("daily", {}).get("temperature_2m_mean", []) if v is not None]
        anomaly = (means[-1] - float(np.mean(means[:-1]))) if len(means) >= 8 else None
        data[region.name] = {
            "temp": float(cur["temperature_2m"]), "humidity": cur.get("relative_humidity_2m"),
            "wind": float(cur.get("wind_speed_10m") or 0.0), "wind_dir": float(cur.get("wind_direction_10m") or 0.0),
            "pressure": float(cur.get("pressure_msl") or 1013.0), "anomaly": anomaly,
            "label": label, "icon": icon,
        }
    return data, payload[0]["current"]["time"][-5:]


def _merge_mm(base: dict, mm: dict) -> dict:
    """Meteomatics değerlerini bölge kayıtlarına işler."""
    data = {}
    for r in REGION_LIST:
        w = dict(base[r.name])
        key = (round(r.lat, 4), round(r.lon, 4))

        def val(param: str) -> float | None:
            return mm.get(param, {}).get(key)

        t, pres, ws, wd, rh, sym = (val(x) for x in MM_CORE + MM_EXTRA)
        if t is not None:
            w["temp"] = t
        if pres is not None:
            w["pressure"] = pres
        if ws is not None:
            w["wind"] = ws * 3.6  # m/s → km/sa
        if wd is not None:
            w["wind_dir"] = wd
        if rh is not None:
            w["humidity"] = rh
        described = describe_symbol(int(sym)) if sym else None
        if described:
            w["label"], w["icon"] = described
        data[r.name] = w
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Geçmiş tarihler: Meteomatics (birincil) + Open-Meteo ERA5 arşivi (hızlı yedek / termal sapma)
# ─────────────────────────────────────────────────────────────────────────────
class DataUnavailable(Exception):
    """Tüm kaynaklar başarısız. Önbelleğe YAZILMAZ; çağıran simülasyona geçer ve RETRY_AFTER sonra yeniden dener."""


_FAILED: dict[tuple, float] = {}

# ── Kota sigortası ───────────────────────────────────────────────────────────
# Open-Meteo ücretsiz kotası konum başına sayar (çok konumlu ve 2 haftadan uzun istekler katlanır): dakikada 600,
# saatte 5.000, günde 10.000. Kota dolunca (HTTP 429) bir süre hiç denenmez; istek beklemeden yedeğe geçer.
_BLOCKED: dict[str, float] = {}
OM_BLOCK_SECONDS = {"Minutely": 60, "Hourly": 900, "Daily": 3600}
MM_HIST_BLOCK_SECONDS = 120          # Meteomatics arşiv isteği zaman aşımına düşerse bu süre atlanır


def _blocked(name: str) -> bool:
    return time.time() < _BLOCKED.get(name, 0.0)


def source_status() -> dict:
    """Arayüz/teşhis için: kota sigortası nedeniyle geçici olarak atlanan kaynaklar ve kalan süre (sn)."""
    now = time.time()
    return {k: round(v - now) for k, v in _BLOCKED.items() if v > now}


def _om_get(params: dict, timeout: float, url: str = OM_ARCHIVE_URL, name: str = "open-meteo-archive") -> list:
    """Open-Meteo isteği (varsayılan: ERA5 arşivi). 429 alırsa kaynağı kotanın türüne göre bir süre kapatır."""
    if _blocked(name):
        raise RuntimeError(f"{name} kotası dolu (geçici olarak atlanıyor)")
    resp = requests.get(url, params=params, timeout=timeout)
    if resp.status_code == 429:
        try:
            reason = resp.json().get("reason", "")
        except ValueError:
            reason = ""
        wait = next((v for k, v in OM_BLOCK_SECONDS.items() if k in reason), 60)
        _BLOCKED[name] = time.time() + wait
        raise RuntimeError(f"Open-Meteo kotası: {reason or 429}")
    resp.raise_for_status()
    items = resp.json()
    return items if isinstance(items, list) else [items]


def mm_hist(params: tuple, locations: str, when: datetime, timeout: float = 12) -> dict:
    """Meteomatics arşiv sorgusu; zaman aşımı ya da bağlantı hatasında kaynağı kısa süre kapatır."""
    if _blocked("meteomatics-archive"):
        raise RuntimeError("Meteomatics arşivi yavaş (geçici olarak atlanıyor)")
    try:
        mm, _ = meteomatics_now(params, locations, timeout=timeout, when=mm_time(when))
        return mm
    except (requests.Timeout, requests.ConnectionError):
        _BLOCKED["meteomatics-archive"] = time.time() + MM_HIST_BLOCK_SECONDS
        raise


# ── Diske kalıcı arşiv önbelleği ─────────────────────────────────────────────
# Geçmiş tarih verisi değişmez: bir kez çekilen tarih data_pipelines/cache/ altına yazılır, uygulama yeniden
# başlasa bile kota harcamadan gelir. Son 7 gün yazılmaz (ERA5 ön sürümü güncellenebilir).
CACHE_DIR = Path(__file__).with_name("cache")


def disk_load(kind: str, when: datetime):
    try:
        return json.loads((CACHE_DIR / f"{kind}_{when:%Y%m%d}.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def disk_save(kind: str, when: datetime, value) -> None:
    if when > NOW - timedelta(days=7):
        return
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        ignore = CACHE_DIR / ".gitignore"
        if not ignore.exists():
            ignore.write_text("*\n", encoding="utf-8")
        (CACHE_DIR / f"{kind}_{when:%Y%m%d}.json").write_text(json.dumps(value, ensure_ascii=False),
                                                              encoding="utf-8")
    except Exception:
        pass


def _guarded(key: tuple, fn, *args):
    """Önbellekli fn'i çağırır; DataUnavailable olursa None döner ve aynı isteği RETRY_AFTER sn boyunca denemez.
    Böylece geçici bir zaman aşımı 30 dakika boyunca önbellekte 'veri yok' olarak kalmaz."""
    if time.time() - _FAILED.get(key, 0.0) < RETRY_AFTER:
        return None
    try:
        return fn(*args)
    except DataUnavailable:
        _FAILED[key] = time.time()
        return None


def run_parallel(*jobs: tuple) -> list:
    """(anahtar, fonksiyon, argümanlar) işlerini aynı anda çalıştırır; her biri `_guarded` korumalıdır.
    Anlık değer ve termal sapma istekleri paralel gider; bekleme süresi toplamı değil en yavaşı kadar olur."""
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
        ctx = get_script_run_ctx()
    except Exception:  # Streamlit dışında (testler)
        ctx, add_script_run_ctx = None, None

    def init() -> None:
        if ctx is not None and add_script_run_ctx is not None:
            add_script_run_ctx(threading.current_thread(), ctx)

    with ThreadPoolExecutor(max_workers=len(jobs), initializer=init) as pool:
        futures = [pool.submit(_guarded, key, fn, *args) for key, fn, args in jobs]
        return [f.result() for f in futures]


def weather_label(temp: float | None, cloud: float | None, rain: float | None) -> tuple[str, str]:
    """Bulut örtüsü (%) ve saatlik yağıştan (mm) hava durumu etiketi (arşivde hava sembolü yok)."""
    if (rain or 0.0) >= 0.2:
        return ("Karlı", "🌨️") if temp is not None and temp <= 0.5 else ("Yağmurlu", "🌧️")
    if cloud is None:
        return "Bilinmiyor", "·"
    return (("Açık", "☀️") if cloud < 20 else ("Az bulutlu", "🌤️") if cloud < 50
            else ("Parçalı bulutlu", "⛅") if cloud < 85 else ("Kapalı", "☁️"))


def om_archive_instant(lats, lons, when: datetime, timeout: float = 20) -> list[dict]:
    """Open-Meteo ERA5 arşivinden belirli saatteki değerler (her nokta için sözlük). Rüzgâr km/sa."""
    day = when.strftime("%Y-%m-%d")
    items = _om_get({
        "latitude": ",".join(f"{v:.4f}" for v in lats), "longitude": ",".join(f"{v:.4f}" for v in lons),
        "start_date": day, "end_date": day, "timezone": "UTC",
        "hourly": "temperature_2m,pressure_msl,wind_speed_10m,wind_direction_10m,relative_humidity_2m,"
                  "cloud_cover,precipitation",
    }, timeout)
    if len(items) != len(lats):
        raise ValueError("eksik arşiv yanıtı")
    out = []
    for it in items:
        h = it["hourly"]
        i = min(when.hour, len(h["time"]) - 1)
        rec = {k: h[k][i] for k in ("temperature_2m", "pressure_msl", "wind_speed_10m", "wind_direction_10m",
                                     "relative_humidity_2m", "cloud_cover", "precipitation")}
        if rec["temperature_2m"] is None or rec["pressure_msl"] is None:
            raise ValueError("arşivde bu tarih için değer yok")
        out.append(rec)
    return out


def om_archive_anomaly(lats, lons, when: datetime, timeout: float = 20) -> list[float | None]:
    """Seçilen günün ortalama sıcaklığı − önceki 30 günün ortalaması (°C), Open-Meteo ERA5 arşivi (~1 sn)."""
    end = when.strftime("%Y-%m-%d")
    start = (when - timedelta(days=30)).strftime("%Y-%m-%d")
    items = _om_get({
        "latitude": ",".join(f"{v:.4f}" for v in lats), "longitude": ",".join(f"{v:.4f}" for v in lons),
        "start_date": start, "end_date": end, "daily": "temperature_2m_mean", "timezone": "UTC",
    }, timeout)
    if len(items) != len(lats):
        raise ValueError("eksik arşiv yanıtı")
    out = []
    for it in items:
        vals = [v for v in it["daily"]["temperature_2m_mean"] if v is not None]
        out.append(vals[-1] - float(np.mean(vals[:-1])) if len(vals) >= 8 else None)
    if all(v is None for v in out):
        raise ValueError("arşivde sapma hesaplanamadı")
    return out


def anomaly_for(lats, lons, mm_locations: str, when: datetime) -> tuple[list[float | None], str]:
    """Termal sapma: önce Open-Meteo arşivi (hızlı), olmazsa Meteomatics zaman serisi. Hepsi olmazsa
    DataUnavailable. Dönüş: (nokta sırasıyla değerler, kaynak adı)."""
    try:
        return om_archive_anomaly(lats, lons, when), "Open-Meteo ERA5"
    except Exception:
        pass
    try:
        if _blocked("meteomatics-archive"):
            raise RuntimeError("Meteomatics arşivi geçici olarak atlanıyor")
        try:
            mm = meteomatics_daily_anomaly(mm_locations, when, timeout=20)
        except (requests.Timeout, requests.ConnectionError):
            _BLOCKED["meteomatics-archive"] = time.time() + MM_HIST_BLOCK_SECONDS
            raise
        return [mm.get((round(float(a), 4), round(float(b), 4))) for a, b in zip(lats, lons)], "Meteomatics"
    except Exception as exc:
        raise DataUnavailable(str(exc)) from exc


HIST_POINT_PARAMS = MM_CORE + ("relative_humidity_2m:p", "total_cloud_cover:p", "precip_1h:mm")


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _hist_points_instant(year: int, month: int | None, day: int | None) -> tuple[list[dict], str]:
    """Tüm bölgelerin seçilen andaki değerleri: Meteomatics (8 sn sınır) → Open-Meteo ERA5 arşivi.

    Meteomatics tek istekte tüm noktaları verir ve Open-Meteo kotası harcamaz; normalde ~1 sn yanıt verir ama yoğun
    anlarda 30–60 sn gecikebiliyor (14.11.2026 ölçümü). Bu yüzden kısa zaman aşımı ve kota sigortası kullanılır;
    takılırsa ERA5 arşivi devreye girer. Başarısızlık önbelleğe yazılmaz, başarılı sonuç diske yazılır.
    """
    when = hist_date(year, month, day)
    cached = disk_load("points", when)
    if cached and len(cached.get("recs", [])) == len(REGION_LIST):
        return cached["recs"], cached["provider"]
    lats, lons = [r.lat for r in REGION_LIST], [r.lon for r in REGION_LIST]
    try:
        mm = mm_hist(HIST_POINT_PARAMS, "+".join(f"{a:.4f},{b:.4f}" for a, b in zip(lats, lons)), when, timeout=8)
        recs = []
        for a, b in zip(lats, lons):
            k = (round(a, 4), round(b, 4))
            g = {p: mm.get(p, {}).get(k) for p in HIST_POINT_PARAMS}
            if g["t_2m:C"] is None:
                raise ValueError("eksik Meteomatics değeri")
            recs.append({"temp": g["t_2m:C"], "pressure": g["msl_pressure:hPa"],
                         "wind": None if g["wind_speed_10m:ms"] is None else g["wind_speed_10m:ms"] * 3.6,
                         "wind_dir": g["wind_dir_10m:d"], "humidity": g["relative_humidity_2m:p"],
                         "cloud": g["total_cloud_cover:p"], "rain": g["precip_1h:mm"]})
        disk_save("points", when, {"recs": recs, "provider": "Meteomatics"})
        return recs, "Meteomatics"
    except Exception:
        pass
    try:
        om = om_archive_instant(lats, lons, when)
        recs = [{"temp": r["temperature_2m"], "pressure": r["pressure_msl"], "wind": r["wind_speed_10m"],
                 "wind_dir": r["wind_direction_10m"], "humidity": r["relative_humidity_2m"],
                 "cloud": r["cloud_cover"], "rain": r["precipitation"]} for r in om]
        disk_save("points", when, {"recs": recs, "provider": "Open-Meteo ERA5"})
        return recs, "Open-Meteo ERA5"
    except Exception as exc:
        raise DataUnavailable(str(exc)) from exc


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _hist_points_anomaly(year: int, month: int | None, day: int | None) -> tuple[list[float | None], str]:
    when = hist_date(year, month, day)
    cached = disk_load("points_anom", when)
    if cached and len(cached.get("values", [])) == len(REGION_LIST):
        return cached["values"], cached["source"]
    lats, lons = [r.lat for r in REGION_LIST], [r.lon for r in REGION_LIST]
    values, src = anomaly_for(lats, lons, "+".join(f"{a:.4f},{b:.4f}" for a, b in zip(lats, lons)), when)
    disk_save("points_anom", when, {"values": values, "source": src})
    return values, src


def _fetch_historical_weather(year: int, month: int | None = None, day: int | None = None,
                              anomaly: bool = True) -> dict:
    """Zamanda yolculuk: seçilen tarih (varsayılan: o yılda bugünün takvim günü), 12:00 UTC.

    Anlık değerler Meteomatics'ten, olmazsa Open-Meteo ERA5 arşivinden gelir. Termal sapma (günün ortalaması −
    önceki 30 gün) önce Open-Meteo arşivinden (hızlı), olmazsa Meteomatics'ten gelir. İkisi de alınamazsa
    mevsimsel simülasyon döner; bu durum önbelleğe yazılmaz ve RETRY_AFTER sn sonra yeniden denenir.

    `anomaly=False`: 30 günlük sapma isteği atılmaz (aralık modunun başlangıç ucu; orada sapma kullanılmaz ve
    Open-Meteo'da bölge başına 2,2 birim harcıyordu). Sapma alanı yerel iklim normalinden doldurulur.
    """
    when = hist_date(year, month, day)
    jobs = [(("w-inst", year, month, day), _hist_points_instant, (year, month, day))]
    if anomaly:
        jobs.append((("w-anom", year, month, day), _hist_points_anomaly, (year, month, day)))
    inst, anom = (run_parallel(*jobs) + [None])[:2]
    if inst is None:
        return _fallback_weather(year, month, day)
    recs, provider = inst
    anomalies, anom_src = anom if anom else ([None] * len(REGION_LIST), "")
    anomaly_kind = "30d" if anom else None
    base = _fallback_weather(year, month, day)["data"]
    data = {}
    for r, rec, an in zip(REGION_LIST, recs, anomalies):
        w = dict(base[r.name])
        for k in ("temp", "pressure", "wind", "wind_dir", "humidity"):
            if rec.get(k) is not None:
                w[k] = float(rec[k])
        if an is None and not anom:
            an = climatology_anomaly(r.name, r.lon, w["temp"], when)
            if an is not None:
                anomaly_kind = "climatology"
        w["anomaly"] = an
        w["label"], w["icon"] = weather_label(rec.get("temp"), rec.get("cloud"), rec.get("rain"))
        data[r.name] = w
    stamp = when.strftime("%d.%m.%Y %H:%M")
    source = f"{provider} · {stamp} UTC"
    if anom_src and anom_src != provider:
        source += f" · sapma: {anom_src}"
    elif anomaly_kind == "climatology":
        source += " · sapma: iklim normaline göre (NASA POWER)"
    elif not anom:
        source += " · sapma alınamadı"
    return {"live": True, "time": stamp, "data": data, "year": year, "month": when.month, "day": when.day,
            "date": when.strftime("%Y-%m-%d"), "provider": provider, "source": source,
            "anomaly_live": anomaly_kind is not None, "anomaly_kind": anomaly_kind}


def _fetch_weather(start_year: int = 0, end_year: int | None = None, month: int | None = None,
                   day: int | None = None) -> dict:
    """Tüm bölgelerin hava verisi.

    - Tek yıl (geriye uyumlu): `_fetch_weather(year)` → 0 canlı veri, aksi halde o yılın bugünkü takvim günü.
    - Yıl aralığı: `_fetch_weather(start_year, end_year)` → bitiş yılının verisi + her bölge için
      `temp_delta`, `pressure_delta`, `wind_delta` (bitiş − başlangıç) ve `*_start` değerleri.
      15.11.2026: ay verilmezse iki yılın SENE ORTALAMASI karşılaştırılır (annual.json; ağ isteği yok, "annual": True).
      Ay verilirse o ayın günü (varsayılan 15'i, 12:00 UTC) iki yılda karşılaştırılır (arşiv istekleri).
    """
    if end_year is None:
        out = _fetch_historical_weather(start_year, month, day) if start_year else _fetch_live_weather()
    elif not month:
        from .annual import _fetch_weather_annual_range
        out = _fetch_weather_annual_range(range_year(start_year), range_year(end_year))
    else:
        out = _fetch_weather_range(int(start_year), int(end_year), month, day)
    return with_source_en(out)


_SOURCE_EN = (   # uzun ifadeler önce
    ("Veri kaynağına ulaşılamadı", "Data source unreachable"),
    ("NASA POWER iklim normali (tahmini)", "NASA POWER climate normal (estimated)"),
    ("iklim normali (tahmini)", "climate normal (estimated)"),
    ("sapma: iklim normaline göre", "anomaly vs climate normal"),
    ("iklim normaline göre", "vs climate normal"),
    ("sapma alınamadı", "anomaly unavailable"),
    ("(Meteomatics'e ulaşılamadı)", "(Meteomatics unreachable)"),
    ("verisine ulaşılamadı", "data unreachable"),
    ("mevsimsel simülasyon", "seasonal simulation"),
    ("yılı simülasyon (tahmini)", "simulated (estimated)"),
    ("Simülasyon (tahmini)", "Simulation (estimated)"),
    ("simülasyon", "simulation"),
    ("sene ortalaması", "year average"),
    ("anomali:", "anomaly:"),
    ("sapma:", "anomaly:"),
    ("arşiv", "archive"),
)


def source_to_en(text: str) -> str:
    """Kaynak satırının İngilizce karşılığı (EN arayüz için)."""
    out = text or ""
    for tr, en in _SOURCE_EN:
        out = out.replace(tr, en)
    return out


def with_source_en(d: dict) -> dict:
    """Dönüş sözlüğüne `source_en` (ve varsa `range_source_en`) ekler; önbellekteki nesneyi değiştirmemek için kopyalar."""
    if not isinstance(d, dict):
        return d
    d = dict(d)
    d.setdefault("source_en", source_to_en(d.get("source", "")))
    if d.get("range_source"):
        d.setdefault("range_source_en", source_to_en(d["range_source"]))
    return d


DELTA_FIELDS = ("temp", "pressure", "wind")   # sıcaklık (°C), deniz seviyesi basıncı (hPa), rüzgâr (km/sa)


def range_year(year: int) -> int:
    """Aralık modunda 0 (canlı) bu yıl sayılır. İki uç da aynı saatte (12:00 UTC) karşılaştırılsın diye canlı
    sorgu yerine aynı takvim gününün arşiv/analiz sorgusu kullanılır; aksi halde gün içi döngü farkı karışır."""
    return int(year) or NOW.year


def range_source(provider: str, s: dict, e: dict) -> str:
    """Aralık verisinin kaynak etiketi: iki uç gerçek, biri simülasyon ya da ikisi de simülasyon."""
    span = f"{s['time']} → {e['time']} UTC"
    if s["live"] and e["live"]:
        return f"{provider} · {span}"
    if s["live"] or e["live"]:
        sim = "başlangıç" if not s["live"] else "bitiş"
        return f"{provider} · {span} · {sim} yılı simülasyon (tahmini)"
    return f"Simülasyon (tahmini) · {span} · {provider} verisine ulaşılamadı"


def _delta(a: float | None, b: float | None) -> float | None:
    return round(float(b) - float(a), 2) if a is not None and b is not None else None


def _fetch_weather_range(start_year: int, end_year: int, month: int | None = None, day: int | None = None) -> dict:
    """İki yılın aynı takvim günü (12:00 UTC) için Meteomatics verisi ve aralarındaki fark.

    Hiçbir koşulda istisna fırlatmaz: uçlardan biri alınamazsa o uç mevsimsel simülasyondur ve
    `delta_live` False olur (fark yine hesaplanır, arayüz 'tahmini' etiketi göstermelidir).
    """
    sy, ey = range_year(start_year), range_year(end_year)
    s = _fetch_historical_weather(sy, month, day, anomaly=False)   # başlangıcın sapması kullanılmaz (kota)
    e = _fetch_historical_weather(ey, month, day)
    data, deltas = {}, {f: {} for f in DELTA_FIELDS}
    for name, w_end in e["data"].items():
        w = dict(w_end)
        w_start = s["data"].get(name, {})
        for f in DELTA_FIELDS:
            w[f"{f}_start"] = w_start.get(f)
            w[f"{f}_delta"] = _delta(w_start.get(f), w_end.get(f))
            if w[f"{f}_delta"] is not None:
                deltas[f][name] = w[f"{f}_delta"]
        data[name] = w
    summary = {}
    for f, vals in deltas.items():
        if vals:
            summary[f] = {"mean": round(float(np.mean(list(vals.values()))), 2),
                          "max_region": max(vals, key=vals.get), "max": max(vals.values()),
                          "min_region": min(vals, key=vals.get), "min": min(vals.values())}
    both = s["live"] and e["live"]
    pa, pb = s.get("provider") or "", e.get("provider") or ""
    source = range_source(pb if pa in ("", pb) else f"{pa} / {pb}", s, e)   # gerçekte kullanılan kaynak(lar)
    return {**e, "data": data, "range": True, "year": ey, "start_year": sy, "end_year": ey,
            "start_time": s["time"], "end_time": e["time"], "start_live": s["live"], "end_live": e["live"],
            "delta_live": both, "delta_summary": summary, "source": source}

@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_live_weather() -> dict:
    """Tüm bölgelerin anlık meteoroloji verisi — çift kaynaklı.

    1. Meteomatics API (HTTPBasicAuth): t_2m, msl_pressure, wind_speed_10m, wind_dir_10m, nem ve hava sembolü.
    2. Open-Meteo: son 30 günün günlük ortalamaları (termal anomali = bugün − 30 gün ortalaması); Meteomatics'e
       ulaşılamazsa anlık değerler de buradan gelir.
    İkisi de başarısızsa uygulama çökmeden mevsimsel simülasyonla sürer. Önbellek 30 dakikada bir yenilenir.
    """
    om = mm = None
    om_stamp = mm_stamp = ""
    try:
        om, om_stamp = _open_meteo_cities()
    except Exception:
        pass
    try:
        mm, mm_stamp = meteomatics_now(MM_CORE + MM_EXTRA,
                                       "+".join(f"{r.lat:.4f},{r.lon:.4f}" for r in REGION_LIST))
    except Exception:
        pass
    if om is None and mm is None:
        return _fallback_weather()

    base = om or _fallback_weather()["data"]
    data = _merge_mm(base, mm) if mm else {k: dict(v) for k, v in base.items()}
    anomaly_kind = "30d" if om is not None else None
    if om is None:      # Open-Meteo yok (ör. kota): 30 günlük sapma yerine iklim normaline göre sapma
        now = datetime.now(timezone.utc)
        for r in REGION_LIST:
            data[r.name]["anomaly"] = climatology_anomaly(r.name, r.lon, data[r.name]["temp"], now)
        if any(w["anomaly"] is not None for w in data.values()):
            anomaly_kind = "climatology"

    if mm:
        provider, stamp = "Meteomatics", mm_stamp
        source = f"Meteomatics · {stamp} UTC" + (" · anomali: Open-Meteo" if om else
                                                  " · sapma: iklim normaline göre (NASA POWER)" if anomaly_kind else "")
    else:
        provider, stamp = "Open-Meteo", om_stamp
        source = f"Open-Meteo · {stamp} UTC (Meteomatics'e ulaşılamadı)"
    return {"live": True, "time": stamp, "data": data, "source": source, "provider": provider,
            "anomaly_live": anomaly_kind is not None, "anomaly_kind": anomaly_kind, "year": 0}



def range_summary_text(result: dict, lang: str = "tr") -> str:
    """Yıl aralığı sonucunun (`_fetch_weather(başlangıç, bitiş)`) tek cümlelik özeti — Seiron notu / bölge kartı için.

    Ör. "2015 → 2024 sene ortalaması: 104 bölgenin 85 tanesi ısındı, ortalama değişim +0,42 °C; en çok ısınan Svalbard ve
    Barents Denizi (+1,85 °C), en çok soğuyan Ross Buz Sahanlığı (−0,90 °C). Kaynak: NASA POWER (MERRA-2)."
    Aralık değilse ya da özet yoksa "". İstisna fırlatmaz.
    """
    try:
        if not result or not result.get("range"):
            return ""
        t = (result.get("delta_summary") or {}).get("temp")
        if not t:
            return ""
        from .regions import REGIONS
        en = lang == "en"
        nm = (lambda n: (REGIONS[n].en[0] or n) if n in REGIONS else n) if en else (lambda n: n)
        vals = [w.get("temp_delta") for w in (result.get("data") or {}).values() if w.get("temp_delta") is not None]
        up, n = sum(1 for v in vals if v > 0), len(vals)
        sy, ey = result.get("start_year"), result.get("end_year")
        annual = bool(result.get("annual"))
        est = not result.get("delta_live", True)

        def f(v):
            return f"{v:+.2f}" if en else f"{v:+.2f}".replace(".", ",").replace("-", "−")
        if en:
            when = f"{sy} → {ey} year average" if annual else f"{result.get('start_time')} → {result.get('end_time')} UTC"
            text = (f"{when}: {up} of {n} regions warmed, mean change {f(t['mean'])} °C; warmed most "
                    f"{nm(t['max_region'])} ({f(t['max'])} °C), cooled most {nm(t['min_region'])} ({f(t['min'])} °C).")
            return text + (" One end is estimated." if est else "")
        when = f"{sy} → {ey} sene ortalaması" if annual else f"{result.get('start_time')} → {result.get('end_time')} UTC"
        text = (f"{when}: {n} bölgenin {up} tanesi ısındı, ortalama değişim {f(t['mean'])} °C; en çok ısınan "
                f"{t['max_region']} ({f(t['max'])} °C), en çok soğuyan {t['min_region']} ({f(t['min'])} °C).")
        return text + (" Bir uç tahminidir." if est else "")
    except Exception:
        return ""
