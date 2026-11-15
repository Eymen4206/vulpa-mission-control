"""Otonom oturum ek fonksiyonları (ÖNERİ #11–#16, #18). Hepsi anlık görüntülerden ya da önbellekten; istisna fırlatmaz.

warming_stripes · warming_ranking · region_export · data_status · season_shift · glossary
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pymannkendall as mk
import streamlit as st

from .annual import BASELINE, load_annual
from .config import ALPHA, END, PERIOD, START, WEATHER_TTL
from .regions import REGION_LIST, REGIONS

MONTHS_TR = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")
ABL_TR = ("tan", "tan", "tan", "dan", "tan", "dan", "dan", "tan", "den", "den", "dan", "tan")   # -den/-dan ünlü/ünsüz uyumu
DAT_TR = ("a", "a", "a", "a", "a", "a", "a", "a", "e", "e", "a", "a")
MONTHS_EN = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
             "November", "December")


def _anomalies(rec: dict) -> tuple[list[int], list[float]] | None:
    base = [t for y, t in zip(rec["years"], rec["T2M"]) if BASELINE[0] <= y <= BASELINE[1]]
    if len(base) < 20:
        return None
    m = float(np.mean(base))
    return list(rec["years"]), [round(t - m, 2) for t in rec["T2M"]]


# ── #11 Isınma şeritleri ────────────────────────────────────────────────────
def warming_stripes(region: str) -> dict | None:
    """Bölgenin yıllık sıcaklık sapmaları (1991–2020 normaline göre) — ısınma şeritleri için.

    Dönüş: {"years", "anomaly" (°C), "vmin": -2.0, "vmax": 2.0 (önerilen renk ölçeği, simetrik), "source",
            "credit_tr", "credit_en"}. Kaynak annual.json (NASA POWER); kayıt yoksa None.
    """
    try:
        rec = load_annual().get("regions", {}).get(region)
        res = _anomalies(rec) if rec else None
    except Exception:
        return None
    if not res:
        return None
    years, an = res
    lim = max(2.0, math.ceil(max(abs(min(an)), abs(max(an))) * 2) / 2)
    return {"years": years, "anomaly": an, "vmin": -lim, "vmax": lim,
            "source": f"NASA POWER (MERRA-2) yıllık ortalamaları · {BASELINE[0]}–{BASELINE[1]} normaline göre",
            "source_en": f"NASA POWER (MERRA-2) annual means · relative to the {BASELINE[0]}–{BASELINE[1]} normal",
            "credit_tr": "Isınma şeritleri fikri: Ed Hawkins (University of Reading), CC BY 4.0",
            "credit_en": "Warming stripes concept: Ed Hawkins (University of Reading), CC BY 4.0"}


# ── #14 Isınma sıralaması ───────────────────────────────────────────────────
@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _ranking() -> list[dict]:
    regions = load_annual().get("regions", {})
    rows = []
    for r in REGION_LIST:
        rec = regions.get(r.name)
        if not rec or len(rec["years"]) < 10:
            continue
        res = mk.original_test(np.asarray(rec["T2M"], dtype=float))
        rows.append({"region": r.name, "per_decade": round(float(res.slope) * 10, 3), "p": float(res.p),
                     "significant": float(res.p) < ALPHA, "years": [rec["years"][0], rec["years"][-1]]})
    rows.sort(key=lambda x: x["per_decade"], reverse=True)
    for i, row in enumerate(rows, 1):
        row["rank"] = i
    return rows


def warming_ranking() -> dict:
    """Tüm bölgelerin yıllık ortalama sıcaklık eğilimi (Sen + Mann-Kendall, annual.json, 1991–son yıl), hızlıdan yavaşa.

    Dönüş: {"rows": [{"rank", "region", "per_decade" (°C/10 yıl), "p", "significant", "years"}], "total",
            "by_region": {ad: rank}, "sentence_tr", "sentence_en"}. Veri yoksa rows boş.
    """
    try:
        rows = _ranking()
    except Exception:
        rows = []
    if not rows:
        return {"rows": [], "total": 0, "by_region": {}, "sentence_tr": "", "sentence_en": ""}
    top = rows[:3]
    en = {r.name: (r.en[0] or r.name) for r in REGION_LIST}
    y0, y1 = rows[0]["years"]
    t_tr = ", ".join(f"{t['region']} ({t['per_decade']:+.2f} °C)".replace(".", ",") for t in top)
    t_en = ", ".join(f"{en[t['region']]} ({t['per_decade']:+.2f} °C)" for t in top)
    return {"rows": rows, "total": len(rows), "by_region": {r["region"]: r["rank"] for r in rows},
            "sentence_tr": f"{y0}–{y1} arasında en hızlı ısınan bölgeler (on yılda): {t_tr} (NASA POWER, Mann-Kendall).",
            "sentence_en": f"Fastest-warming regions over {y0}–{y1} (per decade): {t_en} (NASA POWER, Mann-Kendall)."}


# ── #16 Mevsim değişimi ─────────────────────────────────────────────────────
def season_shift(region: str) -> dict | None:
    """İlk ve son 5 yılın mevsim döngüsü karşılaştırması. Değişim küçükse None (raporda gürültü olmasın).

    Yalnızca gerçek seriler. Gösterilme eşiği: mevsim genliği ≥ 2σ (artık) ve (genlik değişimi ≥ %5 ya da tepe ay 1–2 ay kaymış). Dönüş: {"amp_change_pct", "peak_first", "peak_last",
    "sentence_tr", "sentence_en"} (ay numaraları 1–12).
    """
    if region not in REGIONS:
        return None
    try:
        from .series import analyze, build_series

        from .real_series import series_meta

        if not series_meta(region).get("real"):     # sentetik seride mevsim "değişimi" bilgi değildir
            return None
        spec = REGIONS[region]
        values = build_series(region)[spec.variable].to_numpy(dtype=float)
        r = analyze(region)
        first = values[:60].reshape(-1, PERIOD).mean(axis=0)
        peak_first, peak_last = int(np.argmax(first)) + 1, int(r["peak_month"])
        amp0, amp1 = r["amp_first"], r["amp_last"]
        if amp0 <= 1e-9:
            return None
        pct = (amp1 - amp0) / amp0 * 100
    except Exception:
        return None
    # Mevsim döngüsü gürültüden belirgin değilse (genlik < 2σ) hiçbir şey söylenmez. Tepe ay kayması yalnızca 1–2 ay
    # ise sayılır; daha büyük sıçramalar düz ya da çift tepeli döngünün işaretidir, gerçek bir kayma değildir.
    if min(amp0, amp1) < 2 * r["resid_std"]:
        return None
    gap = min(abs(peak_last - peak_first), 12 - abs(peak_last - peak_first))
    moved = 1 <= gap <= 2
    if abs(pct) < 5 and not moved:
        return None
    y0, y1 = int(START[:4]), int(END[:4])
    parts_tr, parts_en = [], []
    if abs(pct) >= 5:
        parts_tr.append(f"mevsimsel genlik %{abs(pct):.0f} {'arttı' if pct > 0 else 'azaldı'}")
        parts_en.append(f"the seasonal amplitude {'grew' if pct > 0 else 'shrank'} by {abs(pct):.0f}%")
    if moved:
        parts_tr.append(f"tepe ay {MONTHS_TR[peak_first - 1]}'{ABL_TR[peak_first - 1]} "
                        f"{MONTHS_TR[peak_last - 1]}'{DAT_TR[peak_last - 1]} kaydı")
        parts_en.append(f"the peak month moved from {MONTHS_EN[peak_first - 1]} to {MONTHS_EN[peak_last - 1]}")
    return {"amp_change_pct": round(pct, 1), "peak_first": peak_first, "peak_last": peak_last,
            "sentence_tr": f"{y0}–{y0 + 4} ile {y1 - 4}–{y1} karşılaştırıldığında " + " ve ".join(parts_tr) + ".",
            "sentence_en": f"Comparing {y0}–{y0 + 4} with {y1 - 4}–{y1}, " + " and ".join(parts_en) + "."}


# ── #13 Veri durumu ─────────────────────────────────────────────────────────
def data_status() -> dict:
    """Kaynakların anlık durumu ve anlık görüntü tarihleri (Ayarlar → Veri durumu).

    Dönüş: {"sources": [{"id", "name", "state": "ok"|"blocked", "retry_in" (sn|None), "note_tr", "note_en"}],
            "snapshots": [{"id", "name", "generated"}], "checked": "YYYY-MM-DD HH:MM UTC"}
    "blocked" = kota sigortası kaynağı geçici olarak atlıyor (yedek kullanılıyor). Ağ isteği yapmaz.
    """
    from .climatology import load_climatology
    from .real_series import load_snapshot
    from .weather import source_status

    try:
        blocked = source_status()
    except Exception:
        blocked = {}
    names = {"open-meteo-archive": "Open-Meteo ERA5 arşivi", "open-meteo-forecast": "Open-Meteo canlı",
             "meteomatics-archive": "Meteomatics arşivi"}
    sources = []
    for sid, name in names.items():
        wait = blocked.get(sid)
        sources.append({"id": sid, "name": name, "state": "blocked" if wait else "ok", "retry_in": wait,
                        "note_tr": f"Kota/zaman aşımı: {wait} sn sonra yeniden denenecek; yedek kaynak kullanılıyor"
                        if wait else "Kullanılabilir",
                        "note_en": f"Quota/timeout: retry in {wait} s; using a backup source" if wait else "Available"})
    for sid, wait in blocked.items():          # bilinmeyen adlar da görünsün
        if sid not in names:
            sources.append({"id": sid, "name": sid, "state": "blocked", "retry_in": wait,
                            "note_tr": f"{wait} sn sonra yeniden denenecek", "note_en": f"Retry in {wait} s"})

    def gen(fn):
        try:
            return fn().get("generated")
        except Exception:
            return None

    snaps = [{"id": "real_series", "name": "Gerçek tema serileri (ERSST, CO₂, deniz buzu, POWER)", "generated": gen(load_snapshot)},
             {"id": "climatology", "name": "NASA POWER iklim normalleri", "generated": gen(load_climatology)},
             {"id": "annual", "name": "NASA POWER yıllık ortalamalar (1991–)", "generated": gen(load_annual)}]
    return {"sources": sources, "snapshots": snaps,
            "checked": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}


# ── #12 Tekrarlanabilirlik paketi ───────────────────────────────────────────
def region_export(region: str, y0: int | None = None, y1: int | None = None) -> dict | None:
    """Bölgenin tüm sayıları, kaynakları ve yöntem notu (JSON'a hazır, yalnızca temel türler).

    y0, y1: sağ paneldeki NASA POWER penceresi (power_window()). POWER önbellekten gelir.
    """
    if region not in REGIONS:
        return None
    try:
        from .config import LAST_FULL_YEAR, POWER_SPAN
        from .power import _fetch_power, power_years
        from .quality import data_quality
        from .real_series import series_meta
        from .series import analyze

        spec = REGIONS[region]
        r = analyze(region)
        y1 = LAST_FULL_YEAR if y1 is None else int(y1)
        y0 = y1 - POWER_SPAN + 1 if y0 is None else int(y0)
        y0, y1 = power_years(y0, y1)
        pw = _fetch_power(region, y0, y1)
        meta = series_meta(region)
        q = data_quality(region, None, pw.get("live"), pw.get("short_window"))
    except Exception:
        return None

    def clean(d: dict) -> dict:
        return {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in d.items()
                if isinstance(v, (int, float, str, bool, list, np.floating)) or v is None}

    status = data_status()
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "platform": "VULPA Mission Control · NASA Space Apps Challenge 2026",
        "region": {"name": spec.name, "name_en": spec.en[0], "country": spec.country, "lat": spec.lat, "lon": spec.lon,
                   "theme": spec.theme},
        "theme_series": {"variable": spec.variable, "unit": spec.unit, "period": [START, END], "real": meta.get("real"),
                         "kind": meta.get("kind"), "source": meta.get("source"), "description": meta.get("description")},
        "seasonal_mann_kendall": clean(r),
        "nasa_power": clean({k: v for k, v in pw.items() if k not in ("annual_t",)}),
        "nasa_power_annual_t": pw.get("annual_t"),
        "data_quality": q,
        "season_shift": season_shift(region),
        "warming_rank": warming_ranking()["by_region"].get(region),
        "snapshots": status["snapshots"],
        "method": ("Mevsimsel Mann-Kendall testi (periyot 12, pymannkendall); Sen eğilimi her takvim ayının yıllar arası "
                   "farklarının medyanı; projeksiyon Sen doğrusunun 120 ay doğrusal uzatımı (öngörü değildir). NASA POWER "
                   "trendi aynı testle yıllık seriler üzerinden. Veri güveni ölçütleri data_quality.checks içinde."),
    }


# ── #18 Terim sözlüğü ───────────────────────────────────────────────────────
GLOSSARY = {
    "p": ("p-değeri", "p-value",
          "Gerçekte hiçbir eğilim yokken bu kadar güçlü bir eğilimin rastlantıyla görülme olasılığı. 0,05'in altı "
          "\"istatistiksel olarak anlamlı\" kabul edilir; eğilimin büyüklüğünü değil, ne kadar güvenilir olduğunu söyler.",
          "The probability of seeing a trend this strong by chance if there were really no trend. Below 0.05 is "
          "considered statistically significant; it measures reliability, not the size of the trend."),
    "tau": ("Kendall τ", "Kendall τ",
            "Zaman içindeki değişimin ne kadar tutarlı olduğunu gösteren −1 ile +1 arası bir sayı. +1: her yıl bir "
            "öncekinden yüksek; 0: belirgin bir yön yok; −1: sürekli azalma.",
            "A number from −1 to +1 showing how consistent the change over time is. +1: every year higher than the "
            "last; 0: no clear direction; −1: steady decline."),
    "mann_kendall": ("Mann-Kendall testi", "Mann-Kendall test",
                     "Bir serinin zamanla artıp azalmadığını, verinin dağılımı hakkında varsayım yapmadan sınayan test. "
                     "Mevsimsel sürümü her takvim ayını kendi içinde karşılaştırır, böylece mevsim döngüsü eğilim sanılmaz.",
                     "A test of whether a series rises or falls over time without assuming a data distribution. The "
                     "seasonal version compares each calendar month with itself, so the seasonal cycle is not mistaken "
                     "for a trend."),
    "sen": ("Sen eğilimi", "Sen's slope",
            "Eğilimin büyüklüğü: tüm yıl çiftleri arasındaki değişim hızlarının medyanı. Aykırı değerlerden etkilenmez; "
            "birimi \"yılda\" ya da \"on yılda\" değişimdir.",
            "The size of the trend: the median rate of change over all pairs of years. Robust to outliers; expressed "
            "per year or per decade."),
    "anomaly": ("Sapma (anomali)", "Anomaly",
                "Bir değerin uzun dönem ortalamasından (burada çoğunlukla 1991–2020 normalinden) farkı. +1 °C, normalden "
                "1 derece sıcak demektir.",
                "The difference between a value and its long-term average (here mostly the 1991–2020 normal). +1 °C "
                "means one degree warmer than normal."),
    "normal": ("İklim normali", "Climate normal",
               "Dünya Meteoroloji Örgütü'nün standart 30 yıllık referans ortalaması (1991–2020). Sapmalar buna göre "
               "hesaplanır.",
               "The World Meteorological Organization's standard 30-year reference average (1991–2020); anomalies are "
               "measured against it."),
    "aod": ("AOD (aerosol optik derinliği)", "AOD (aerosol optical depth)",
            "Havadaki toz, duman ve kirlilik parçacıklarının güneş ışığını ne kadar engellediğinin ölçüsü. 0,1 berrak, "
            "1'in üstü çok puslu hava demektir.",
            "How much dust, smoke and pollution particles block sunlight. 0.1 is clear air; above 1 is very hazy."),
    "spei": ("SPEI", "SPEI",
             "Standartlaştırılmış Yağış-Buharlaşma İndeksi: yağış ile buharlaşma ihtiyacı arasındaki farkın z-skoru. "
             "−1'in altı kuraklık, +1'in üstü olağandışı nem demektir.",
             "Standardised Precipitation-Evapotranspiration Index: a z-score of precipitation minus evaporative demand. "
             "Below −1 indicates drought, above +1 unusual wetness."),
    "merra2": ("MERRA-2", "MERRA-2",
               "NASA'nın uydu ve yer gözlemlerini bir hava modeliyle birleştiren yeniden analiz veri seti (1980–). NASA "
               "POWER değerleri buradan gelir.",
               "NASA's reanalysis combining satellite and ground observations with a weather model (1980–). NASA POWER "
               "values come from it."),
    "era5": ("ERA5", "ERA5",
             "Avrupa Orta Vadeli Hava Tahminleri Merkezi'nin (ECMWF) saatlik küresel yeniden analizi; geçmiş tarihlerin "
             "hava değerleri için kullanılır.",
             "ECMWF's hourly global reanalysis, used for weather values on historical dates."),
    "sst": ("Deniz yüzeyi sıcaklığı (SST)", "Sea surface temperature (SST)",
            "Okyanusun en üst katmanının sıcaklığı. Okyanuslar ısının çoğunu depoladığı için iklim değişiminin en "
            "güvenilir göstergelerinden biridir.",
            "The temperature of the ocean's top layer. Oceans store most of the extra heat, so it is one of the most "
            "reliable climate-change indicators."),
    "projection": ("Projeksiyon", "Projection",
                   "Sen doğrusunun 2034'e doğrusal uzatımı. Bir öngörü değildir; eğilim aynen sürerse ne olacağını gösterir.",
                   "A linear extension of the Sen line to 2034. Not a forecast: it shows what happens if the trend simply "
                   "continues."),
    "confidence": ("Veri güveni", "Data confidence",
                   "Sonuca ne kadar güvenilebileceğinin özeti: veri gerçek mi, test koşulları sağlanıyor mu, kaynaklar "
                   "canlı mı.",
                   "A summary of how far the result can be trusted: is the data observed, are the test conditions met, "
                   "are the sources live."),
}


def glossary(lang: str = "tr") -> dict:
    """Terim sözlüğü: {anahtar: {"term", "text"}} seçili dilde. Anahtarlar: p, tau, mann_kendall, sen, anomaly, normal,
    aod, spei, merra2, era5, sst, projection, confidence. Ham TR/EN için GLOSSARY."""
    i = 1 if lang == "en" else 0
    return {k: {"term": v[i], "text": v[2 + i]} for k, v in GLOSSARY.items()}
