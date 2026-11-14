"""Canlı ve arşiv hava durumu: Meteomatics (anlık / arşiv) + Open-Meteo (30 günlük anomali, yedek).

app.py içindeki fonksiyonların birebir kopyası; ağ ya da kimlik doğrulama hatasında istisna fırlatmaz,
mevsimsel simülasyona geçer. Dil/arayüz yardımcıları (compass, wlabel, weather_sentence …) app.py'de kalır.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta

import numpy as np
import requests
import streamlit as st
from requests.auth import HTTPBasicAuth

from .config import MM_CORE, MM_EXTRA, MM_URL, NOW, WEATHER_TTL, hist_date
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



def _fallback_weather(year: int = 0) -> dict:
    """Ağ yoksa: mevsim ve enlem kuşağına dayalı tutarlı yaklaşık değerler (açıkça 'tahmini' etiketlenir)."""
    month = NOW.month
    data = {}
    for r in REGION_LIST:
        alat = abs(r.lat)
        season = math.cos(2 * math.pi * (month - (7 if r.lat >= 0 else 1)) / 12)
        temp = 27 - 0.42 * alat + 9 * season * min(1.0, alat / 35)
        # Genel dolaşım: tropiklerde alize (doğudan), orta enlemlerde batı rüzgârları, kutuplarda doğudan
        wind_dir = 90.0 if alat < 30 else (270.0 if alat < 60 else 90.0)
        pressure = 1010 + 10 * math.exp(-((alat - 30) / 10) ** 2) - 8 * math.exp(-((alat - 60) / 8) ** 2)
        data[r.name] = {"temp": temp, "humidity": None, "wind": 15.0, "wind_dir": wind_dir, "pressure": pressure,
                        "anomaly": 0.0, "label": "Tahmini", "icon": "≈"}
    stamp = hist_date(year).strftime("%d.%m.%Y %H:%M") if year else NOW.strftime("%H:%M")
    return {"live": False, "time": stamp, "data": data, "year": year,
            "source": "Veri kaynağına ulaşılamadı · mevsimsel simülasyon", "provider": "Simülasyon",
            "anomaly_live": False}


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


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_historical_weather(year: int) -> dict:
    """Zamanda yolculuk: seçilen yılda bugünün takvim günü (12:00 UTC) için Meteomatics arşiv verisi.
    Termal anomali, o günün 24 saatlik ortalamasının önceki 30 günün ortalamasından sapmasıdır."""
    when = hist_date(year)
    locs = "+".join(f"{r.lat:.4f},{r.lon:.4f}" for r in REGION_LIST)
    # Not: weather_symbol_1h arşivde sunulmuyor (tüm isteği düşürür); hava durumu bulut ve yağıştan türetilir.
    try:
        mm, _ = meteomatics_now(MM_CORE + ("relative_humidity_2m:p", "total_cloud_cover:p", "precip_1h:mm"),
                                locs, when=mm_time(when))
    except Exception:
        return _fallback_weather(year)
    try:
        anomaly = meteomatics_daily_anomaly(locs, when)
    except Exception:
        anomaly = {}
    data = _merge_mm(_fallback_weather(year)["data"], mm)
    for r in REGION_LIST:
        key = (round(r.lat, 4), round(r.lon, 4))
        w = data[r.name]
        w["anomaly"] = anomaly.get(key)
        cloud = mm.get("total_cloud_cover:p", {}).get(key)
        rain = mm.get("precip_1h:mm", {}).get(key) or 0.0
        if rain >= 0.2:
            w["label"], w["icon"] = ("Karlı", "🌨️") if w["temp"] <= 0.5 else ("Yağmurlu", "🌧️")
        elif cloud is not None:
            w["label"], w["icon"] = (("Açık", "☀️") if cloud < 20 else ("Az bulutlu", "🌤️") if cloud < 50
                                     else ("Parçalı bulutlu", "⛅") if cloud < 85 else ("Kapalı", "☁️"))
        else:
            w["label"], w["icon"] = "Bilinmiyor", "·"
    stamp = when.strftime("%d.%m.%Y %H:%M")
    return {"live": True, "time": stamp, "data": data, "year": year, "provider": "Meteomatics",
            "source": f"Meteomatics · {stamp} UTC", "anomaly_live": bool(anomaly)}


def _fetch_weather(start_year: int = 0, end_year: int | None = None) -> dict:
    """50 bölge hava verisi.

    - Tek yıl (geriye uyumlu): `_fetch_weather(year)` → 0 canlı veri, aksi halde o yılın bugünkü takvim günü.
    - Yıl aralığı: `_fetch_weather(start_year, end_year)` → bitiş yılının verisi + her bölge için
      `temp_delta`, `pressure_delta`, `wind_delta` (bitiş − başlangıç) ve `*_start` değerleri.
    """
    if end_year is None:
        return _fetch_historical_weather(start_year) if start_year else _fetch_live_weather()
    return _fetch_weather_range(int(start_year), int(end_year))


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


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_weather_range(start_year: int, end_year: int) -> dict:
    """İki yılın aynı takvim günü (12:00 UTC) için Meteomatics verisi ve aralarındaki fark.

    Hiçbir koşulda istisna fırlatmaz: uçlardan biri alınamazsa o uç mevsimsel simülasyondur ve
    `delta_live` False olur (fark yine hesaplanır, arayüz 'tahmini' etiketi göstermelidir).
    """
    sy, ey = range_year(start_year), range_year(end_year)
    s = _fetch_historical_weather(sy)
    e = _fetch_historical_weather(ey)
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
    source = range_source("Meteomatics", s, e)
    return {**e, "data": data, "range": True, "year": ey, "start_year": sy, "end_year": ey,
            "start_time": s["time"], "end_time": e["time"], "start_live": s["live"], "end_live": e["live"],
            "delta_live": both, "delta_summary": summary, "source": source}

@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_live_weather() -> dict:
    """50 bölgenin anlık meteoroloji verisi — çift kaynaklı.

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
    if om is None:
        for w in data.values():
            w["anomaly"] = None

    if mm:
        provider, stamp = "Meteomatics", mm_stamp
        source = f"Meteomatics · {stamp} UTC" + (" · anomali: Open-Meteo" if om else "")
    else:
        provider, stamp = "Open-Meteo", om_stamp
        source = f"Open-Meteo · {stamp} UTC (Meteomatics'e ulaşılamadı)"
    return {"live": True, "time": stamp, "data": data, "source": source, "provider": provider,
            "anomaly_live": om is not None, "year": 0}

