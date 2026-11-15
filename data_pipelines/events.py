# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""NASA EONET doğal olayları (Earth Observatory Natural Event Tracker, v3) — anahtarsız.

Kürede "Klasik" katmanda açılıp kapanan olay işaretleri için. Tek istek, 30 dk önbellek, istisna fırlatmaz.
Kaynak: https://eonet.gsfc.nasa.gov/api/v3/events (NASA Earth Science Data Systems).
"""

from __future__ import annotations

import time

import requests
import streamlit as st

from .config import RETRY_AFTER, WEATHER_TTL

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
MAX_EVENTS = 150

# EONET kategori kimliği → kısa tür anahtarı (Frontend simge/renk seçer) ve TR/EN ad
EVENT_TYPES = {
    "wildfires": ("wildfire", "Orman yangını", "Wildfire"),
    "severeStorms": ("storm", "Şiddetli fırtına", "Severe storm"),
    "volcanoes": ("volcano", "Volkan", "Volcano"),
    "seaLakeIce": ("ice", "Deniz/göl buzu", "Sea & lake ice"),
    "floods": ("flood", "Sel", "Flood"),
    "drought": ("drought", "Kuraklık", "Drought"),
    "dustHaze": ("dust", "Toz ve pus", "Dust & haze"),
    "earthquakes": ("earthquake", "Deprem", "Earthquake"),
    "landslides": ("landslide", "Heyelan", "Landslide"),
    "snow": ("snow", "Kar", "Snow"),
    "tempExtremes": ("temperature", "Aşırı sıcaklık", "Temperature extreme"),
    "waterColor": ("water", "Su rengi", "Water colour"),
    "manmade": ("manmade", "İnsan kaynaklı", "Manmade"),
}


class _Unavailable(Exception):
    """İstek başarısız: önbelleğe yazılmaz."""


_FAILED_AT = [0.0]


def _point(geom: dict) -> tuple[float, float] | None:
    """EONET geometrisinden (lat, lon). Point: [lon, lat]; Polygon: ilk halkanın ağırlık merkezi."""
    coords = geom.get("coordinates")
    try:
        if geom.get("type") == "Point":
            return float(coords[1]), float(coords[0])
        ring = coords[0]
        lons = [float(p[0]) for p in ring]
        lats = [float(p[1]) for p in ring]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    except Exception:
        return None


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_events_cached(days: int) -> list[dict]:
    try:
        resp = requests.get(EONET_URL, params={"status": "open", "days": days}, timeout=20)
        resp.raise_for_status()
        events = resp.json().get("events", [])
    except Exception as exc:
        raise _Unavailable(str(exc)) from exc
    out = []
    for ev in events:
        geoms = [g for g in ev.get("geometry", []) if g.get("coordinates")]
        if not geoms:
            continue
        last = max(geoms, key=lambda g: g.get("date") or "")       # çok noktalı olaylarda (fırtına izi) son konum
        pt = _point(last)
        if pt is None or not (-90 <= pt[0] <= 90 and -180 <= pt[1] <= 180):
            continue
        cat = (ev.get("categories") or [{}])[0].get("id", "")
        kind, name_tr, name_en = EVENT_TYPES.get(cat, ("other", "Diğer", "Other"))
        src = (ev.get("sources") or [{}])[0]
        out.append({"id": ev.get("id", ""), "title": ev.get("title", ""), "type": kind,
                    "type_tr": name_tr, "type_en": name_en,
                    "lat": round(pt[0], 3), "lon": round(pt[1], 3), "date": (last.get("date") or "")[:10],
                    "source_url": src.get("url") or ev.get("link", ""), "source": src.get("id", "")})
    out.sort(key=lambda e: e["date"], reverse=True)
    return out[:MAX_EVENTS]


def fetch_events(days: int = 30) -> list[dict]:
    """Son `days` gündeki açık EONET olayları (en yeni önce, en fazla 150).

    Her olay: {"id", "title", "type", "type_tr", "type_en", "lat", "lon", "date" (YYYY-MM-DD), "source_url", "source"}.
    `type` değerleri: wildfire, storm, volcano, ice, flood, drought, dust, earthquake, landslide, snow, temperature,
    water, manmade, other. Çok noktalı olaylarda (fırtına izi) yalnızca son konum döner.
    Kaynağa ulaşılamazsa boş liste döner (önbelleğe yazılmaz, RETRY_AFTER sn sonra yeniden denenir). İstisna fırlatmaz.
    Olaylar canlıdır; zamanda yolculuk seçiliyken gösterilmemesi önerilir.
    """
    if time.time() - _FAILED_AT[0] < RETRY_AFTER:
        return []
    try:
        return _fetch_events_cached(int(days))
    except _Unavailable:
        _FAILED_AT[0] = time.time()
        return []
    except Exception:
        return []
