"""Bölge tema serileri için GERÇEK veri — yalnızca anahtar gerektirmeyen kaynaklar.

50 bölgenin 33'ü artık ölçüm/yeniden analiz verisine dayanır; kalan 17'si (FWI, NDVI, deniz seviyesi, PM2.5,
buzul alanı, yeraltı suyu, kar örtüsü) anahtarsız ve uzun geçmişli bir kaynak bulunamadığı için sentetik kalır.

Kaynaklar:
    NASA POWER (MERRA-2)   — aylık T2M, TS, T2M_MAX, PRECTOTCORR_SUM, AOD_55; günlük T2M/T2M_MAX/T2M_MIN/
                             PRECTOTCORR/TOA_SW_DWN (SPEI-3 için)
    NOAA ERSST v5 (ERDDAP) — aylık deniz yüzeyi sıcaklığı (2° ızgara)
    NOAA GML               — Mauna Loa aylık atmosferik CO₂
    NSIDC Sea Ice Index v4 — Güney Yarımküre aylık deniz buzu yayılımı

Çalışma düzeni (hız + dayanıklılık):
    1. `snapshots/real_series.json` — depoya işlenmiş anlık görüntü. 2000–2024 dönemi değişmediği için çoğu
       çalıştırmada ağ isteği yapılmaz; sayfa hızlı açılır, internet yokken de gerçek veri gösterilir.
    2. Anlık görüntüde olmayan bölge → canlı istek (`@st.cache_data(ttl=1800)`).
    3. İkisi de olmazsa `None` döner; `series.build_series` sentetik seriye geçer. İstisna fırlatılmaz.

Anlık görüntüyü yenilemek için:  `.venv\\Scripts\\python -m data_pipelines.refresh_series`
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

from .config import END, START, WEATHER_TTL
from .regions import REGIONS

SNAPSHOT_PATH = Path(__file__).with_name("snapshots") / "real_series.json"
POWER_MONTHLY_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
ERSST_URL = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/nceiErsstv5.csv"
CO2_URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"
SEAICE_URL = "https://noaadata.apps.nsidc.org/NOAA/G02135/{hemi}/monthly/data/{H}_{mm:02d}_extent_v4.0.csv"

Y0, Y1 = int(START[:4]), int(END[:4])
DATES = pd.date_range(START, END, freq="MS")

# Seri türü → (açıklama, kaynak etiketi). Bölge değişken adları ve birimleri regions.py'de buna göre ayarlıdır.
KINDS: dict[str, tuple[str, str]] = {
    "t2m":      ("Aylık ortalama 2 m hava sıcaklığı (°C)", "NASA POWER · MERRA-2 T2M"),
    "t2m_anom": ("2 m sıcaklık anomalisi: aylık değer − aynı ayın 2000–2024 ortalaması (°C)", "NASA POWER · MERRA-2 T2M"),
    "ts_anom":  ("Yer yüzeyi (deri) sıcaklığı anomalisi (°C)", "NASA POWER · MERRA-2 TS"),
    "t2m_max":  ("Ayın en yüksek 2 m sıcaklığı (°C)", "NASA POWER · MERRA-2 T2M_MAX"),
    "precip":   ("Aylık toplam yağış (mm)", "NASA POWER · MERRA-2 PRECTOTCORR_SUM"),
    "spei3":    ("SPEI-3 yaklaşımı: 3 aylık (yağış − Hargreaves PET), takvim ayına göre z-skoru",
                 "NASA POWER · MERRA-2 (yağış, T2M, T2M_MAX/MIN, TOA radyasyonu)"),
    "aod":      ("Aerosol optik derinliği, 550 nm (2000 yılı aylık ortalamayla doldurulur)", "NASA POWER · MERRA-2 AOD_55"),
    "sst":      ("Aylık deniz yüzeyi sıcaklığı (°C), en yakın 2° deniz hücresi", "NOAA ERSST v5 (ERDDAP)"),
    "co2":      ("Mauna Loa aylık ortalama atmosferik CO₂ (ppm)", "NOAA GML Mauna Loa Gözlemevi"),
    "seaice_s": ("Güney Yarımküre aylık deniz buzu yayılımı (milyon km²)", "NSIDC Sea Ice Index v4"),
    "gwetroot": ("Kök bölgesi toprak nemi (0 kuru – 1 doygun)", "NASA POWER · MERRA-2 GWETROOT"),
    "gwettop":  ("Yüzey toprak nemi (0 kuru – 1 doygun)", "NASA POWER · MERRA-2 GWETTOP"),
    "snodp":    ("Aylık ortalama kar derinliği (cm)", "NASA POWER · MERRA-2 SNODP"),
}

# Bölge (iç kimlik) → seri türü. Burada olmayan bölgeler sentetik kalır.
REAL_SOURCES: dict[str, str] = {
    "Marmara Havzası": "t2m",
    "Batı Avrupa Ovası": "t2m_anom",
    "Britanya Adaları": "t2m_anom",
    "Sibirya Taygası": "ts_anom",
    "İber Platosu": "t2m_max",
    "Apenin Yarımadası": "spei3",
    "Alp Kuşağı": "t2m_anom",
    "Antarktika Yarımadası": "seaice_s",
    "Arap Körfezi Kıyı Çölü": "t2m_max",
    "Necd Platosu": "t2m_max",
    "Sahra Çölü": "aod",
    "Doğu Afrika Savanları": "spei3",
    "Cape Floristik Bölgesi": "precip",
    "Kongo Havzası": "aod",
    "Etiyopya Yaylası": "precip",
    "Kanto Ovası": "t2m",
    "Kore Yarımadası": "t2m",
    "Batı Ghatlar": "precip",
    "İndus Havzası": "t2m_max",
    "Ganj-Brahmaputra Deltası": "precip",
    "Malakka Boğazı": "sst",
    "Filipin Denizi": "sst",
    "Büyük Set Resifi": "sst",
    "Mauna Loa (Kuzey Pasifik)": "co2",
    "Meksika Vadisi": "t2m",
    "Büyük Göller Havzası": "t2m_anom",
    "Alaska Permafrost Kuşağı": "ts_anom",
    "Amazon Havzası": "aod",
    "Atlantik Ormanı": "precip",
    "Pampa Ovaları": "t2m",
    "Humboldt Akıntısı": "sst",
    "Orta Şili": "precip",
    "Kuzey And Paramoları": "precip",
    # 14.11.2026: önceden sentetik olan 17 bölge, değişken seçici sayesinde gerçek NASA/NOAA serilerine atandı.
    # Değişken adı ölçülen şeyi söyler (ör. PM2.5 yerine AOD, NDVI yerine toprak nemi); tema başlığı aynen kalır.
    "Akdeniz Maki Kuşağı": "gwettop",
    "Grönland Buz Tabakası": "ts_anom",
    "Nil Deltası ve Vadisi": "spei3",
    "İran Platosu": "spei3",
    "Nijer Deltası": "sst",
    "Kuzey Çin Ovası": "aod",
    "Yangtze Deltası": "sst",
    "Hint-Ganj Ovası": "aod",
    "Chao Phraya Deltası": "precip",
    "Cava Kuzey Kıyısı": "sst",
    "Moğol Bozkırı ve Gobi": "spei3",
    "ABD Doğu Kıyısı": "sst",
    "Kanada Kuzey Ormanları": "spei3",
    "Kaliforniya Çaparalı": "spei3",
    "Florida Everglades": "sst",
    "Pasifik Kıyı Dağları": "snodp",
    "Tropikal And Buzulları": "t2m_anom",
}

SYNTHETIC_REASON = ("Anahtarsız ve 2000'den bu yana kesintisiz bir kaynak bulunamadı (FWI, NDVI, deniz seviyesi, "
                    "PM2.5, buzul alanı, yeraltı suyu ve kar örtüsü için Earthdata/Copernicus hesabı gerekir).")


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────────────────────────────────────
def _align(series: pd.Series) -> tuple[np.ndarray, int]:
    """Seriyi START–END aylık eksenine oturtur. Eksik aylar o takvim ayının ortalamasıyla doldurulur.
    Dönüş: (değerler, doldurulan ay sayısı).

    Kaynakların tarih damgası tutarsız olabilir (ör. ERSST 2008'den sonra ayın 1'i yerine 15'ini kullanır);
    bu yüzden her tarih önce ait olduğu ayın başına indirgenir."""
    series = pd.Series(series.to_numpy(dtype=float),
                       index=pd.to_datetime(series.index).to_period("M").to_timestamp())
    s = series.groupby(level=0).mean().reindex(DATES)
    missing = int(s.isna().sum())
    if missing:
        clim = s.groupby(s.index.month).transform("mean")
        s = s.fillna(clim).interpolate(limit_direction="both")
    if s.isna().any():
        raise ValueError("seri doldurulamadı")
    return s.to_numpy(dtype=float), missing


def _anomaly(values: np.ndarray) -> np.ndarray:
    month = DATES.month.to_numpy()
    clim = np.array([values[month == m].mean() for m in range(1, 13)])
    return values - clim[month - 1]


def _power_monthly(lat: float, lon: float, params: str) -> dict[str, pd.Series]:
    resp = requests.get(POWER_MONTHLY_URL, params={
        "parameters": params, "community": "AG", "format": "JSON",
        "latitude": round(lat, 4), "longitude": round(lon, 4), "start": Y0, "end": Y1,
    }, timeout=40)
    resp.raise_for_status()
    out = {}
    for name, values in resp.json()["properties"]["parameter"].items():
        pairs = {pd.Timestamp(int(k[:4]), int(k[4:]), 1): (v if v > -900 else np.nan)
                 for k, v in values.items() if k[4:] != "13"}          # "YYYY13" = yıllık değer
        out[name] = pd.Series(pairs).sort_index()
    return out


def _spei3(lat: float, lon: float) -> pd.Series:
    """SPEI-3 yaklaşımı. Günlük Hargreaves PET = 0,0023 · Ra · (Tort + 17,8) · √(Tmaks − Tmin);
    Ra (MJ/m²/gün) × 0,408 → mm/gün. D = yağış − PET aylık toplanır, 3 aylık kayan toplam alınır ve her takvim
    ayı kendi içinde z-skoruna çevrilir (log-lojistik dağılım yerine normal yaklaşım)."""
    resp = requests.get(POWER_DAILY_URL, params={
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,TOA_SW_DWN", "community": "AG", "format": "JSON",
        "latitude": round(lat, 4), "longitude": round(lon, 4), "start": f"{Y0}0101", "end": f"{Y1}1231",
    }, timeout=60)
    resp.raise_for_status()
    par = resp.json()["properties"]["parameter"]
    d = pd.DataFrame({k: pd.Series(v) for k, v in par.items()})
    d.index = pd.to_datetime(d.index, format="%Y%m%d")
    d = d.where(d > -900).interpolate(limit_direction="both")
    ra_mm = 0.408 * d["TOA_SW_DWN"]
    pet = 0.0023 * ra_mm * (d["T2M"] + 17.8) * np.sqrt((d["T2M_MAX"] - d["T2M_MIN"]).clip(lower=0))
    balance = (d["PRECTOTCORR"] - pet).resample("MS").sum()
    acc = balance.rolling(3, min_periods=1).sum()
    grp = acc.groupby(acc.index.month)
    return (acc - grp.transform("mean")) / grp.transform("std")


def _ersst(lat: float, lon: float) -> pd.Series:
    """En yakın 2° ERSST hücresi; kara hücresine düşerse komşu hücreler denenir."""
    base_lat, base_lon = round(lat / 2) * 2, (round(lon / 2) * 2) % 360
    for dlat, dlon in ((0, 0), (0, 2), (0, -2), (2, 0), (-2, 0), (2, 2), (-2, -2), (2, -2), (-2, 2)):
        la, lo = base_lat + dlat, (base_lon + dlon) % 360
        q = f"sst[({START}):1:({END})][(0.0)][({la})][({lo})]"
        resp = requests.get(f"{ERSST_URL}?{q}", timeout=40)
        if resp.status_code != 200:
            continue
        df = pd.read_csv(io.StringIO(resp.text), skiprows=[1])
        s = pd.Series(df["sst"].to_numpy(dtype=float), index=pd.to_datetime(df["time"]).dt.tz_localize(None))
        if s.notna().mean() > 0.9:
            return s
    raise ValueError("ERSST deniz hücresi bulunamadı")


def _co2() -> pd.Series:
    resp = requests.get(CO2_URL, timeout=40)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), comment="#")
    df = df[df["average"] > 0]
    return pd.Series(df["average"].to_numpy(dtype=float),
                     index=[pd.Timestamp(int(y), int(m), 1) for y, m in zip(df["year"], df["month"])])


def _seaice_south() -> pd.Series:
    rows = {}
    for mm in range(1, 13):
        resp = requests.get(SEAICE_URL.format(hemi="south", H="S", mm=mm), timeout=40)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), skipinitialspace=True)
        df.columns = [c.strip() for c in df.columns]
        for y, m, ext in zip(df["year"], df["mo"], df["extent"]):
            if float(ext) > 0:
                rows[pd.Timestamp(int(y), int(m), 1)] = float(ext)
    return pd.Series(rows).sort_index()


# ─────────────────────────────────────────────────────────────────────────────
# Tek bölge için gerçek seri (önbelleksiz çekirdek — anlık görüntü betiği de bunu kullanır)
# ─────────────────────────────────────────────────────────────────────────────
def fetch_real_series(region_name: str) -> dict | None:
    """Bölgenin gerçek serisini kaynaktan çeker. Dönüş: {"kind", "source", "values" (300 değer), "filled"} ya da
    bölge gerçek veri listesinde değilse None. Ağ hatasında istisna FIRLATIR (çağıran yakalar)."""
    kind = REAL_SOURCES.get(region_name)
    if kind is None:
        return None
    spec = REGIONS[region_name]
    if kind in ("t2m", "t2m_anom", "ts_anom", "t2m_max", "precip", "aod", "gwetroot", "gwettop", "snodp"):
        param = {"t2m": "T2M", "t2m_anom": "T2M", "ts_anom": "TS", "t2m_max": "T2M_MAX",
                 "precip": "PRECTOTCORR_SUM", "aod": "AOD_55", "gwetroot": "GWETROOT", "gwettop": "GWETTOP",
                 "snodp": "SNODP"}[kind]
        raw = _power_monthly(spec.lat, spec.lon, param)[param]
    elif kind == "spei3":
        raw = _spei3(spec.lat, spec.lon)
    elif kind == "sst":
        raw = _ersst(spec.lat, spec.lon)
    elif kind == "co2":
        raw = _co2()
    else:
        raw = _seaice_south()
    values, filled = _align(raw)
    if kind in ("t2m_anom", "ts_anom"):
        values = _anomaly(values)
    return {"kind": kind, "source": KINDS[kind][1], "values": [round(float(v), 4) for v in values],
            "filled": filled}


# ─────────────────────────────────────────────────────────────────────────────
# Çalışma zamanı: anlık görüntü → canlı istek → None
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def load_snapshot() -> dict:
    try:
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        if data.get("period") == [START, END]:
            return data
    except Exception:
        pass
    return {"regions": {}}


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_real_cached(region_name: str) -> dict | None:
    try:
        return fetch_real_series(region_name)
    except Exception:
        return None


def real_series(region_name: str) -> dict | None:
    """Gerçek seri kaydı ({"kind", "source", "values", "filled", "origin"}) ya da None (sentetik kullanılacak)."""
    if region_name not in REAL_SOURCES:
        return None
    snap = load_snapshot()["regions"].get(region_name)
    if snap and len(snap.get("values", [])) == len(DATES):
        return {**snap, "origin": "snapshot", "fetched": load_snapshot().get("generated")}
    live = _fetch_real_cached(region_name)
    return {**live, "origin": "live"} if live else None


def series_meta(region_name: str) -> dict:
    """Arayüz için: bölge serisi gerçek mi, kaynağı ne?

    {"real": bool, "kind": str | None, "source": str, "description": str, "origin": "snapshot"|"live"|"synthetic",
     "filled_months": int, "note": str}
    """
    rec = real_series(region_name)
    if rec:
        return {"real": True, "kind": rec["kind"], "source": rec["source"], "description": KINDS[rec["kind"]][0],
                "origin": rec["origin"], "filled_months": rec.get("filled", 0),
                "note": f"Gerçek veri · {rec['source']} · {START[:4]}–{END[:4]}"}
    kind = REAL_SOURCES.get(region_name)
    note = ("Gerçek veri kaynağına ulaşılamadı; geçici olarak sentetik seri gösteriliyor." if kind
            else "Sentetik prototip verisi. " + SYNTHETIC_REASON)
    return {"real": False, "kind": None, "source": REGIONS[region_name].source, "description": "",
            "origin": "synthetic", "filled_months": 0, "note": note}


def write_snapshot(records: dict[str, dict]) -> Path:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "period": [START, END],
               "kinds": {k: {"description": v[0], "source": v[1]} for k, v in KINDS.items()},
               "regions": records}
    SNAPSHOT_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return SNAPSHOT_PATH


# Tema serisinin veri türü (arayüz etiketi): model / uydu ölçümü / yerinde ölçüm — kaynakla birlikte
_KIND_TYPE = {"sst": ("Yerinde ölçüm (NOAA ERSST)", "In-situ (NOAA ERSST)"),
              "co2": ("Yerinde ölçüm (NOAA Mauna Loa)", "In-situ (NOAA Mauna Loa)"),
              "seaice_s": ("Uydu ölçümü (NSIDC)", "Satellite (NSIDC)")}


def theme_type_label(region_name: str, lang: str = "tr") -> str:
    """Bölge tema serisinin tür etiketi: "Model (MERRA-2)" / "Uydu ölçümü (NSIDC)" / "Yerinde ölçüm (NOAA …)"."""
    kind = (series_meta(region_name) or {}).get("kind")
    tr, en = _KIND_TYPE.get(kind, ("Model (MERRA-2)", "Model (MERRA-2)"))
    return en if lang == "en" else tr
