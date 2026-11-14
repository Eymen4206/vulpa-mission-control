"""Veri güveni rozeti (ÖNERİ #3): bölge kartındaki sonuçlara ne kadar güvenilebileceğinin şeffaf özeti.

Ağ isteği yapmaz. Hava ve NASA POWER durumları Frontend'in zaten çektiği sonuçlardan parametre olarak verilir.
"""

from __future__ import annotations

import streamlit as st

from .config import WEATHER_TTL
from .real_series import series_meta
from .regions import REGIONS
from .series import analyze

RHO_LIMIT = 0.5

SHORT = {
    ("real", True): ("Gerçek gözlem verisi", "Observed data"),
    ("real", False): ("Sentetik prototip seri", "Synthetic prototype series"),
    ("autocorr", True): ("Otokorelasyon düşük", "Low autocorrelation"),
    ("autocorr", False): ("Otokorelasyon yüksek", "High autocorrelation"),
    ("consistency", True): ("Eğilim tutarlı", "Consistent trend"),
    ("consistency", False): ("Eğilim döneme duyarlı", "Period-sensitive trend"),
    ("weather", True): ("Hava verisi ölçümden", "Measured weather"),
    ("weather", False): ("Hava verisi tahmini", "Estimated weather"),
    ("power", True): ("NASA POWER ölçümü", "NASA POWER data"),
    ("power", False): ("NASA POWER simülasyon", "NASA POWER simulated"),
    ("window", True): ("Trend penceresi yeterli", "Trend window sufficient"),
    ("window", False): ("Trend penceresi kısa", "Trend window short"),
}       # artık otokorelasyon bunun üstündeyse Mann-Kendall p-değeri olduğundan küçük çıkabilir


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _series_checks(region: str) -> list[dict]:
    meta = series_meta(region)
    r = analyze(region)
    checks = []
    if meta.get("real"):
        checks.append({"key": "real", "ok": True,
                       "text_tr": f"Tema serisi gerçek gözlem: {meta.get('source', '')}",
                       "text_en": f"Theme series is observed data: {meta.get('source', '')}"})
    else:
        checks.append({"key": "real", "ok": False,
                       "text_tr": "Tema serisi sentetik prototip verisi (gerçek ölçüm değil)",
                       "text_en": "Theme series is synthetic prototype data (not a measurement)"})
    rho = r["rho1"]
    checks.append({"key": "autocorr", "ok": rho <= RHO_LIMIT,
                   "text_tr": (f"Artıklarda otokorelasyon düşük (ρ₁ = {rho:.2f})" if rho <= RHO_LIMIT else
                               f"Artıklarda otokorelasyon yüksek (ρ₁ = {rho:.2f}); p-değeri olduğundan küçük görünebilir"),
                   "text_en": (f"Low residual autocorrelation (ρ₁ = {rho:.2f})" if rho <= RHO_LIMIT else
                               f"High residual autocorrelation (ρ₁ = {rho:.2f}); the p-value may look smaller than it is")})
    # Yalnızca gerçek bir yön değişimi sayılır: yarıların eğimleri ters işaretli VE en az biri kendi içinde belirgin (p < 0,1).
    # Aksi hâlde kısa yarı-dönemlerdeki gürültü güveni gereksiz yere düşürürdü.
    flipped = (r["s1"] > 0) != (r["s2"] > 0) and abs(r["s1"]) > 1e-12 and abs(r["s2"]) > 1e-12
    same = not (flipped and min(r["p1"], r["p2"]) < 0.1)
    checks.append({"key": "consistency", "ok": bool(same),
                   "text_tr": ("Eğilim dönemin iki yarısında aynı yönde" if same else
                               "Eğilim dönemin iki yarısında ters yönde; sonuç döneme duyarlı"),
                   "text_en": ("Trend has the same direction in both halves of the period" if same else
                               "Trend reverses between the two halves; the result is period-sensitive")})
    return checks


def data_quality(region: str, weather_live: bool | None = None, power_live: bool | None = None,
                 power_short: bool | None = None) -> dict | None:
    """Bölge kartı için veri güveni.

    Parametreler (isteğe bağlı, Frontend'in elindeki sonuçlardan): weather_live = fetch_weather()["live"],
    power_live = fetch_power(city)["live"], power_short = fetch_power(city)["short_window"]. None ise o ölçüt atlanır.

    Dönüş: {"level": "high"|"medium"|"low", "score": 0–100,
            "checks": [{"key", "ok", "text_tr", "text_en", "short_tr", "short_en"}],
            "reasons_tr": [...], "reasons_en": [...]}   # reasons_* = olumsuz ölçütler (yoksa olumlu özet)
    Kural: tema serisi sentetikse seviye her zaman "low". Gerçekse her olumsuz ölçüt bir basamak düşürür
    (0 → high, 1 → medium, 2+ → low). İstisna fırlatmaz; bilinmeyen bölgede None.
    """
    if region not in REGIONS:
        return None
    try:
        checks = list(_series_checks(region))
    except Exception:
        return None
    if weather_live is not None:
        checks.append({"key": "weather", "ok": bool(weather_live),
                       "text_tr": "Hava verisi ölçüm/arşivden" if weather_live else
                       "Hava kaynaklarına ulaşılamadı; iklim normali (tahmini) gösteriliyor",
                       "text_en": "Weather comes from measurements/archive" if weather_live else
                       "Weather sources unavailable; climate normal (estimate) shown"})
    if power_live is not None:
        checks.append({"key": "power", "ok": bool(power_live),
                       "text_tr": "Uzun vadeli trend NASA POWER ölçümünden" if power_live else
                       "NASA POWER'a ulaşılamadı; uzun vadeli trend simülasyon",
                       "text_en": "Long-term trend from NASA POWER data" if power_live else
                       "NASA POWER unavailable; long-term trend is simulated"})
    if power_short is not None:
        checks.append({"key": "window", "ok": not power_short,
                       "text_tr": "Trend penceresi yeterince uzun" if not power_short else
                       "Trend penceresi kısa; Mann-Kendall güvenilirliği sınırlı",
                       "text_en": "Trend window is long enough" if not power_short else
                       "Trend window is short; Mann-Kendall reliability is limited"})
    for c in checks:                       # dar açılır kutular için kısa etiketler (en fazla ~32 karakter)
        c["short_tr"], c["short_en"] = SHORT.get((c["key"], c["ok"]), (c["text_tr"], c["text_en"]))
    bad = [c for c in checks if not c["ok"]]
    synthetic = any(c["key"] == "real" and not c["ok"] for c in checks)
    level = "low" if synthetic or len(bad) >= 2 else ("medium" if bad else "high")
    score = max(0, round(100 * (len(checks) - len(bad)) / len(checks)) - (40 if synthetic else 0))
    if bad:
        reasons_tr, reasons_en = [c["text_tr"] for c in bad], [c["text_en"] for c in bad]
    else:
        reasons_tr = ["Tüm ölçütler olumlu: gerçek veri, tutarlı ve anlamlı test koşulları"]
        reasons_en = ["All checks pass: observed data, consistent and valid test conditions"]
    return {"level": level, "score": score, "checks": checks, "reasons_tr": reasons_tr, "reasons_en": reasons_en}
