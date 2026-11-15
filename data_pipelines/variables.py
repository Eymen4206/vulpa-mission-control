"""Değişken seçimi ve nokta analizi (Büyük Plan, Aşama A: madde 1, 2, 5, 6, 7).

Kaynak: NASA POWER aylık uç noktası (MERRA-2), anahtarsız. Bir nokta için tek istek tüm değişkenleri getirir
(30 dk bellek önbelleği + kalıcı disk önbelleği; nokta 0,5°'ye yuvarlanır = MERRA-2 ızgara aralığı).
Sahte veri üretilmez: kaynak alınamazsa `available=False` ve açıklama döner. İstisna fırlatmaz.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pymannkendall as mk
import requests
import streamlit as st
from scipy import stats

from .config import ALPHA, LAST_FULL_YEAR, WEATHER_TTL

POWER_MONTHLY_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
SPAN_YEARS = 25
CACHE_DIR = Path(__file__).with_name("cache")
_BLOCK = {"until": 0.0}
_DAYS = (31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

# key: (POWER parametresi, kategori, birim, dönüşüm, Giovanni MERRA-2 aylık veri kimliği | None,
#       ad TR, ad EN, tanım TR, tanım EN, neden TR, neden EN, uygun bölge türleri)
# Dönüşüm: "id" aynı; "mm_month" mm/gün → mm/ay (ayın gün sayısıyla).
VARIABLES: dict[str, tuple] = {
    "T2M": ("T2M", "temperature", "°C", "id", "M2TMNXSLV_5_12_4_T2M",
            "Hava sıcaklığı (2 m)", "Air temperature (2 m)",
            "Yerden 2 metre yükseklikteki havanın aylık ortalama sıcaklığı.",
            "Monthly mean air temperature 2 metres above the ground.",
            "Sera gazları arttıkça küresel ölçekte yükselmesi beklenir; şehirlerde ısı adası etkisi ekler.",
            "Expected to rise globally as greenhouse gases increase; cities add an urban heat-island effect.",
            ("city", "desert", "polar", "mountain", "agriculture", "taiga", "savanna")),
    "T2M_MAX": ("T2M_MAX", "temperature", "°C", "id", None,
                "En yüksek sıcaklık", "Maximum temperature",
                "Ay içindeki en sıcak anın sıcaklığı (2 m).", "The hottest temperature of the month (2 m).",
                "Sıcak hava dalgalarının sıklaşması en çok bu değişkende görünür.",
                "More frequent heatwaves show up most clearly in this variable.",
                ("city", "desert", "agriculture")),
    "T2M_MIN": ("T2M_MIN", "temperature", "°C", "id", None,
                "En düşük sıcaklık", "Minimum temperature",
                "Ay içindeki en soğuk anın sıcaklığı (2 m).", "The coldest temperature of the month (2 m).",
                "Geceler gündüzlerden hızlı ısınabilir; don olaylarının azalması burada görünür.",
                "Nights can warm faster than days; fewer frosts show up here.",
                ("city", "mountain", "agriculture", "taiga")),
    "TS": ("TS", "temperature", "°C", "id", "M2TMNXSLV_5_12_4_TS",
           "Yüzey (deri) sıcaklığı", "Surface (skin) temperature",
           "Toprağın, buzun ya da denizin en üst yüzeyinin sıcaklığı.",
           "Temperature of the very top surface of land, ice or sea.",
           "Buz ve kar eridikçe yüzey koyulaşır ve daha hızlı ısınır.",
           "As ice and snow melt the surface darkens and warms faster.",
           ("polar", "desert", "ocean", "coast")),
    "PRECTOTCORR": ("PRECTOTCORR", "water", "mm/ay", "mm_month", "M2TMNXFLX_5_12_4_PRECTOTCORR",
                    "Yağış", "Precipitation",
                    "Bir ayda düşen toplam yağmur ve kar (düzeltilmiş, mm).",
                    "Total rain and snow falling in a month (bias-corrected, mm).",
                    "Isınan hava daha fazla nem taşır: bazı bölgeler ıslanır, bazıları kurur — aynı süreç, zıt "
                    "yönlü trendler.",
                    "Warmer air holds more moisture: some regions get wetter, others drier — one process, opposite "
                    "trends.",
                    ("rainforest", "savanna", "agriculture", "desert", "coast", "mountain")),
    "EVLAND": ("EVLAND", "water", "mm/ay", "mm_month", "M2TMNXLND_5_12_4_EVLAND",
               "Buharlaşma (kara)", "Evaporation (land)",
               "Topraktan ve bitkilerden havaya geçen su miktarı (mm/ay).",
               "Water moving from soil and plants into the air (mm/month).",
               "Sıcaklık artınca buharlaşma artar; su azsa toprak kurur.",
               "Evaporation rises with temperature; where water is scarce the soil dries out.",
               ("agriculture", "rainforest", "savanna", "taiga")),
    "RH2M": ("RH2M", "atmosphere", "%", "id", None,
             "Bağıl nem", "Relative humidity",
             "Havanın taşıyabileceği en fazla nemin yüzde kaçını taşıdığı (2 m).",
             "How much moisture the air holds as a percentage of the maximum it could hold (2 m).",
             "Karalarda sıcaklık nemden hızlı arttığı için bağıl nem sıklıkla düşer.",
             "Over land temperature often rises faster than moisture, so relative humidity tends to fall.",
             ("desert", "city", "agriculture")),
    "QV2M": ("QV2M", "atmosphere", "g/kg", "id", "M2TMNXSLV_5_12_4_QV2M",
             "Özgül nem", "Specific humidity",
             "Bir kilogram havadaki su buharı miktarı (gram).", "Grams of water vapour in one kilogram of air.",
             "Isınan atmosfer daha fazla su buharı tutar (derece başına yaklaşık %7).",
             "A warmer atmosphere holds more water vapour (about 7% per degree).",
             ("ocean", "coast", "rainforest")),
    "WS10M": ("WS10M", "atmosphere", "m/s", "id", None,
              "Rüzgâr hızı (10 m)", "Wind speed (10 m)",
              "Yerden 10 metre yükseklikteki aylık ortalama rüzgâr hızı.", "Monthly mean wind speed 10 metres up.",
              "Kara yüzeyinde rüzgârların yavaşladığı (\"stilling\") birçok bölgede gözlenmiştir.",
              "Surface winds have slowed (\"stilling\") in many land regions.",
              ("coast", "ocean", "mountain")),
    "CLOUD_AMT": ("CLOUD_AMT", "atmosphere", "%", "id", "M2TMNXRAD_5_12_4_CLDTOT",
                  "Bulutluluk", "Cloud amount",
                  "Gökyüzünün yüzde kaçının bulutla kaplı olduğu.", "Percentage of the sky covered by cloud.",
                  "Bulutlar güneşi yansıtır; değişimleri bölgesel ısınmayı hızlandırabilir ya da yavaşlatabilir.",
                  "Clouds reflect sunlight; changes can speed up or slow down regional warming.",
                  ("ocean", "rainforest", "coast")),
    "ALLSKY_SFC_SW_DWN": ("ALLSKY_SFC_SW_DWN", "energy", "MJ/m²/gün", "id", "M2TMNXRAD_5_12_4_SWGDN",
                          "Güneş ışınımı (yüzey)", "Solar radiation (surface)",
                          "Yüzeye ulaşan güneş enerjisi (bulutlar dahil).",
                          "Sunlight energy reaching the surface (including cloud effects).",
                          "Hava kirliliği azalınca yüzeye daha fazla güneş ulaşır (\"aydınlanma\").",
                          "When air pollution falls, more sunlight reaches the surface (\"brightening\").",
                          ("city", "desert", "agriculture")),
    "AOD_55": ("AOD_55", "atmosphere", "AOD", "id", "M2TMNXAER_5_12_4_TOTEXTTAU",
               "Aerosol (toz/duman)", "Aerosol (dust/smoke)",
               "Havadaki toz, duman ve kirlilik parçacıklarının güneşi ne kadar engellediği (550 nm).",
               "How much dust, smoke and pollution particles block sunlight (550 nm).",
               "Sanayi, yangınlar ve çöl tozuyla artar; temiz hava yasalarıyla azalır.",
               "Rises with industry, fires and desert dust; falls with clean-air laws.",
               ("city", "desert", "savanna")),
    "GWETROOT": ("GWETROOT", "soil", "0–1", "id", "M2TMNXLND_5_12_4_GWETROOT",
                 "Kök bölgesi toprak nemi", "Root-zone soil moisture",
                 "Bitki köklerinin bulunduğu katmandaki toprağın ıslaklığı (0 kuru, 1 doygun).",
                 "Wetness of the soil layer where plant roots are (0 dry, 1 saturated).",
                 "Kuraklıkların ve tarım stresinin en doğrudan göstergesi.",
                 "The most direct indicator of drought and crop stress.",
                 ("agriculture", "savanna", "rainforest", "taiga")),
    "GWETTOP": ("GWETTOP", "soil", "0–1", "id", "M2TMNXLND_5_12_4_GWETTOP",
                "Yüzey toprak nemi", "Surface soil moisture",
                "Toprağın en üst birkaç santimetresinin ıslaklığı (0 kuru, 1 doygun).",
                "Wetness of the top few centimetres of soil (0 dry, 1 saturated).",
                "Yağış ve buharlaşmadaki değişimlere en hızlı tepki veren katman.",
                "The layer that responds fastest to changes in rain and evaporation.",
                ("agriculture", "desert", "savanna")),
    "SNODP": ("SNODP", "ice", "cm", "id", "M2TMNXLND_5_12_4_SNODP",
              "Kar derinliği", "Snow depth",
              "Yerdeki kar örtüsünün aylık ortalama kalınlığı.", "Monthly mean thickness of snow on the ground.",
              "Isınma kar mevsimini kısaltır ve kar örtüsünü inceltir.",
              "Warming shortens the snow season and thins the snow cover.",
              ("mountain", "polar", "taiga")),
}
CATEGORIES = {"temperature": ("Sıcaklık", "Temperature"), "water": ("Su döngüsü", "Water cycle"),
              "atmosphere": ("Atmosfer", "Atmosphere"), "energy": ("Enerji", "Energy"),
              "soil": ("Toprak", "Soil"), "ice": ("Kar ve buz", "Snow & ice")}
LAND_ONLY = ("EVLAND", "GWETROOT", "GWETTOP", "SNODP")



def _latlon(lat: float, lon: float, lang: str = "tr") -> str:
    """38.5, 22.5 → "38,5°K, 22,5°D" (TR) / "38.5°N, 22.5°E" (EN): koordinat olduğu başlıkta anlaşılsın."""
    ns, ew = (("N", "S"), ("E", "W")) if lang == "en" else (("K", "G"), ("D", "B"))
    a = f"{abs(lat):.1f}°{ns[0] if lat >= 0 else ns[1]}"
    b = f"{abs(lon):.1f}°{ew[0] if lon >= 0 else ew[1]}"
    if lang != "en":
        a, b = a.replace(".", ","), b.replace(".", ",")
    return f"{a}, {b}"

def variable_catalog(lang: str = "tr") -> list[dict]:
    """Seçilebilir değişkenler (kategori sırasıyla). Her öğe: {key, power_param, category, category_name, name, unit,
    definition, why, good_for, land_only, giovanni (bool)}."""
    en = lang == "en"
    out = []
    for cat in CATEGORIES:
        for key, v in VARIABLES.items():
            if v[1] != cat:
                continue
            unit = v[2].replace("mm/ay", "mm/month").replace("gün", "day") if en else v[2]
            out.append({"key": key, "power_param": v[0], "category": cat, "category_name": CATEGORIES[cat][1 if en else 0],
                        "name": v[6] if en else v[5], "unit": unit, "definition": v[8] if en else v[7],
                        "why": v[10] if en else v[9], "good_for": list(v[11]), "land_only": key in LAND_ONLY,
                        "giovanni": v[4] is not None})
    return out


# ── Veri çekme ──────────────────────────────────────────────────────────────
def _snap(lat: float, lon: float) -> tuple[float, float]:
    """0,5°'ye yuvarlar; enlemi ±89,5'e sıkıştırır, boylamı −180…180 aralığına getirir (ör. 200° → −160°)."""
    lat = max(-89.5, min(89.5, float(lat)))
    lon = ((float(lon) + 180.0) % 360.0) - 180.0
    la, lo = round(round(lat * 2) / 2, 1), round(round(lon * 2) / 2, 1)
    return la, (-180.0 if lo == 180.0 else lo)


def _disk_path(lat: float, lon: float, y0: int, y1: int) -> Path:
    return CACHE_DIR / f"power_{lat:+06.1f}_{lon:+07.1f}_{y0}_{y1}.json"


def _disk_load(lat, lon, y0, y1):
    try:
        return json.loads(_disk_path(lat, lon, y0, y1).read_text(encoding="utf-8"))
    except Exception:
        return None


def _disk_save(lat, lon, y0, y1, value) -> None:
    if y1 >= LAST_FULL_YEAR + 1:
        return
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        ignore = CACHE_DIR / ".gitignore"
        if not ignore.exists():
            ignore.write_text("*\n", encoding="utf-8")
        _disk_path(lat, lon, y0, y1).write_text(json.dumps(value), encoding="utf-8")
    except Exception:
        pass


class _Unavailable(Exception):
    pass


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _point_raw(lat: float, lon: float, y0: int, y1: int) -> dict:
    """{"elev", "params": {param: {"YYYYMM": değer}}} — başarısızlık önbelleğe yazılmaz (istisna)."""
    cached = _disk_load(lat, lon, y0, y1)
    if cached:
        return cached
    if time.time() < _BLOCK["until"]:
        raise _Unavailable("NASA POWER geçici olarak atlanıyor (kota)")
    try:
        resp = requests.get(POWER_MONTHLY_URL, params={
            "parameters": ",".join(v[0] for v in VARIABLES.values()), "community": "AG", "format": "JSON",
            "latitude": lat, "longitude": lon, "start": y0, "end": y1}, timeout=60)
        if resp.status_code == 429:
            _BLOCK["until"] = time.time() + 60
            raise _Unavailable("NASA POWER kotası (429)")
        resp.raise_for_status()
        js = resp.json()
        out = {"elev": float(js["geometry"]["coordinates"][2]), "params": js["properties"]["parameter"]}
    except _Unavailable:
        raise
    except Exception as exc:
        raise _Unavailable(str(exc)) from exc
    _disk_save(lat, lon, y0, y1, out)
    return out


def _window(end_year: int | None) -> tuple[int, int]:
    y1 = min(int(end_year or LAST_FULL_YEAR), LAST_FULL_YEAR)
    return y1 - SPAN_YEARS + 1, y1


def point_data(lat: float, lon: float, end_year: int | None = None) -> dict:
    """Noktanın ham verisi. Dönüş: {"ok", "lat", "lon" (0,5°'ye yuvarlanmış), "elev", "y0", "y1", "params", "error"}."""
    la, lo = _snap(lat, lon)
    y0, y1 = _window(end_year)
    try:
        raw = _point_raw(la, lo, y0, y1)
        return {"ok": True, "lat": la, "lon": lo, "elev": raw["elev"], "y0": y0, "y1": y1, "params": raw["params"],
                "error": None}
    except Exception as exc:
        return {"ok": False, "lat": la, "lon": lo, "elev": None, "y0": y0, "y1": y1, "params": {}, "error": str(exc)}


def variable_series(lat: float, lon: float, key: str, end_year: int | None = None) -> dict:
    """Aylık seri. Dönüş: {"key", "dates" (YYYY-MM), "values" (None = eksik), "unit", "available", "reason", "source",
    "live", "lat", "lon", "y0", "y1"}."""
    v = VARIABLES.get(key)
    pd_ = point_data(lat, lon, end_year)
    base = {"key": key, "unit": v[2] if v else "", "lat": pd_["lat"], "lon": pd_["lon"], "y0": pd_["y0"],
            "y1": pd_["y1"], "live": pd_["ok"], "source": f"NASA POWER (MERRA-2) aylık · {pd_['y0']}–{pd_['y1']}",
            "source_en": f"NASA POWER (MERRA-2) monthly · {pd_['y0']}–{pd_['y1']}"}
    if v is None:
        return {**base, "dates": [], "values": [], "available": False, "reason": "bilinmeyen değişken"}
    if not pd_["ok"]:
        return {**base, "dates": [], "values": [], "available": False,
                "reason": f"NASA POWER'a ulaşılamadı ({pd_['error']}); biraz sonra yeniden deneyin."}
    par = pd_["params"].get(v[0], {})
    dates, vals = [], []
    for y in range(pd_["y0"], pd_["y1"] + 1):
        for m in range(1, 13):
            x = par.get(f"{y}{m:02d}")
            dates.append(f"{y}-{m:02d}")
            if x is None or x < -900:
                vals.append(None)
            else:
                vals.append(round(x * _DAYS[m - 1], 2) if v[3] == "mm_month" else round(float(x), 4))
    missing = sum(x is None for x in vals)
    finite = [x for x in vals if x is not None]
    if missing > len(vals) * 0.1:
        reason = ("Bu değişken bu noktada yok: toprak nemi, buharlaşma ve kar yalnızca buzsuz kara için "
                  "hesaplanır (deniz ve kalıcı buz örtüsünde yoktur)." if key in LAND_ONLY
                  else "Bu noktada verinin %10'undan fazlası eksik.")
        return {**base, "dates": dates, "values": vals, "available": False, "reason": reason}
    if finite and max(finite) - min(finite) < 1e-9:
        return {**base, "dates": dates, "values": vals, "available": False,
                "reason": "Değişken bu noktada sabit ya da ölçüm hassasiyetinin altında (ör. kutupta aerosol ≈ 0, "
                           "tropikte kar yok); trend hesaplanamaz."}
    return {**base, "dates": dates, "values": vals, "available": True, "reason": None}


# ── Analiz ──────────────────────────────────────────────────────────────────
def _fill(vals: list) -> np.ndarray:
    """Az sayıdaki eksik ayı aynı takvim ayının ortalamasıyla doldurur (yalnızca <%10 eksikte çağrılır)."""
    a = np.array([np.nan if x is None else x for x in vals], dtype=float)
    for m in range(12):
        col = a[m::12]
        if np.isnan(col).any():
            col[np.isnan(col)] = np.nanmean(col)
            a[m::12] = col
    return a


def _sen_ci(annual: np.ndarray) -> tuple[float, float]:
    n = len(annual)
    slopes = np.sort([(annual[j] - annual[i]) / (j - i) for i in range(n) for j in range(i + 1, n)])
    c = 1.96 * math.sqrt(n * (n - 1) * (2 * n + 5) / 18)
    m1 = int(max(0, math.floor((len(slopes) - c) / 2)))
    m2 = int(min(len(slopes) - 1, math.ceil((len(slopes) + c) / 2)))
    return float(slopes[m1]), float(slopes[m2])


def analyze_values(values, start_year: int, unit: str = "", name: str = "") -> dict:
    """Aylık seri (12'nin katı) için: mevsimsel Mann-Kendall + Sen (%95 GA), otokorelasyon düzeltmeli t-testi,
    anlamlılık için gereken yıl (Weatherhead 1998), mevsimden arındırılmış seri ve yıllık ortalamalar."""
    a = _fill(list(values)) if any(x is None for x in values) else np.asarray(values, dtype=float)
    n = len(a) - len(a) % 12
    a = a[:n]
    years_n = n // 12
    res = mk.seasonal_test(a, period=12)
    per_year = float(res.slope)
    annual = a.reshape(years_n, 12).mean(axis=1)
    sen_basis = "seasonal"
    if per_year == 0.0:
        # Kaba hassasiyetli verilerde (ör. NASA POWER toprak nemi 2 ondalık) aylar arası farkların medyanı tam 0'a
        # yuvarlanabilir; yıllık ortalamalar daha ince çözünürlüklüdür. Sen eğimi bu durumda yıllık seriden alınır.
        alt = float(mk.original_test(annual).slope)
        if alt != 0.0:
            per_year, sen_basis = alt, "annual"
    ci_low, ci_high = _sen_ci(annual)
    clim = a.reshape(years_n, 12).mean(axis=0)
    anom = a - np.tile(clim, years_n)                        # mevsimden arındırılmış (aylık anomali)
    t_years = np.arange(n) / 12.0
    lr = stats.linregress(t_years, anom)
    resid = anom - (lr.intercept + lr.slope * t_years)
    rho = float(np.corrcoef(resid[:-1], resid[1:])[0, 1]) if np.std(resid) > 0 else 0.0
    rho = min(max(rho, -0.99), 0.99)
    n_eff = max(3.0, n * (1 - rho) / (1 + rho))
    se_adj = lr.stderr * math.sqrt((n - 2) / max(n_eff - 2, 1)) if lr.stderr > 0 else float("inf")
    t_val = lr.slope / se_adj if se_adj not in (0, float("inf")) else 0.0
    p_t = float(2 * stats.t.sf(abs(t_val), max(n_eff - 2, 1)))
    sig_mk, sig_t = float(res.p) < ALPHA, p_t < ALPHA
    # Weatherhead vd. (1998): n* = [3.3 σN / |ω0| · √((1+φ)/(1−φ))]^(2/3) yıl
    sigma = float(np.std(resid, ddof=1))
    omega = abs(lr.slope)
    if omega > 0 and sigma > 0:
        need = (3.3 * sigma / omega * math.sqrt((1 + rho) / (1 - rho))) ** (2 / 3)
    else:
        need = float("inf")
    yts = {"years_needed": None if math.isinf(need) else round(need, 1), "years_available": years_n,
           "extra_years": None if math.isinf(need) else max(0, math.ceil(need - years_n)), "significant_now": sig_mk}
    dec = per_year * 10
    return {"n": n, "years": years_n, "start_year": start_year, "end_year": start_year + years_n - 1,
            "mk": {"trend": res.trend, "p": float(res.p), "z": float(res.z), "tau": float(res.Tau), "significant": sig_mk},
            "sen": {"per_year": per_year, "per_decade": dec, "ci_low": ci_low * 10, "ci_high": ci_high * 10,
                    "ci_unit": "per_decade", "basis": sen_basis},
            "ttest": {"slope_per_decade": float(lr.slope) * 10, "t": float(t_val), "p": p_t, "significant": sig_t,
                      "n_eff": round(n_eff, 1), "rho1": round(rho, 3)},
            # Aynı karar: ikisi de anlamlı (ve aynı yönde) ya da ikisi de anlamsız
            "agree": sig_mk == sig_t and (not sig_mk or (dec >= 0) == (lr.slope >= 0)),
            "years_to_significance": yts,
            "annual": {"years": list(range(start_year, start_year + years_n)), "values": [round(float(x), 4) for x in annual]},
            "deseasonalized": [round(float(x), 4) for x in anom],
            "unit": unit, "name": name}


def _yts_sentences(a: dict) -> tuple[str, str]:
    y = a["years_to_significance"]
    if a["mk"]["significant"]:
        return "Eğilim zaten istatistiksel olarak anlamlı.", "The trend is already statistically significant."
    if y["years_needed"] is None:
        return ("Belirgin bir eğilim yok; daha uzun veri de sonucu değiştirmeyebilir.",
                "There is no clear trend; a longer record may not change this.")
    if y["extra_years"] == 0:
        return ("Eğilim sınırda: veri süresi yeterli ama gürültü yüksek.",
                "The trend is borderline: the record is long enough but noise is high.")
    return (f"Bu eğilim aynı hızla sürerse yaklaşık {y['extra_years']} yıl daha veriyle anlamlı hale gelir "
            f"(toplam ≈{y['years_needed']:.0f} yıl; Weatherhead vd. 1998).",
            f"If the trend continues at this rate it would become significant with about {y['extra_years']} more "
            f"years of data (≈{y['years_needed']:.0f} years in total; Weatherhead et al. 1998).")


_REASON_EN = {
    "Bu değişken bu noktada yok: toprak nemi, buharlaşma ve kar yalnızca buzsuz kara için hesaplanır (deniz ve "
    "kalıcı buz örtüsünde yoktur).":
        "This variable is not available here: soil moisture, evaporation and snow are computed only for ice-free "
        "land (not over the sea or permanent ice sheets).",
    "Bu noktada verinin %10'undan fazlası eksik.": "More than 10% of the data is missing at this point.",
    "Değişken bu noktada sabit ya da ölçüm hassasiyetinin altında (ör. kutupta aerosol ≈ 0, tropikte kar yok); "
    "trend hesaplanamaz.":
        "The variable is constant here or below measurement precision (e.g. aerosol ≈ 0 at the pole, no snow in the "
        "tropics); no trend can be computed.",
    "bilinmeyen değişken": "unknown variable",
}


def _reason_en(reason: str | None) -> str | None:
    if not reason:
        return None
    if reason.startswith("NASA POWER'a ulaşılamadı"):
        return "NASA POWER could not be reached; please try again shortly."
    if reason.startswith("analiz yapılamadı"):
        return "The analysis could not be computed."
    return _REASON_EN.get(reason, reason)


def giovanni_url(key: str, lat: float, lon: float, y0: int, y1: int) -> str | None:
    """NASA Giovanni 'alan ortalamalı zaman serisi' bağlantısı (MERRA-2 aylık). Karşılığı olmayan değişkende None.
    Giovanni ücretsiz NASA Earthdata hesabı isteyebilir."""
    v = VARIABLES.get(key)
    if not v or not v[4]:
        return None
    d = 0.5
    bbox = f"{lon - d:.2f},{lat - d:.2f},{lon + d:.2f},{lat + d:.2f}"
    return (f"https://giovanni.gsfc.nasa.gov/giovanni/#service=ArAvTs&starttime={y0}-01-01T00:00:00Z"
            f"&endtime={y1}-12-31T23:59:59Z&bbox={bbox}&data={v[4]}")


def variable_analysis(lat: float, lon: float, key: str, end_year: int | None = None) -> dict:
    """Seçilen nokta ve değişken için tam analiz (Büyük Plan şeması). Veri yoksa available=False + reason."""
    s = variable_series(lat, lon, key, end_year)
    v = VARIABLES.get(key)
    head = {"key": key, "name": v[5] if v else key, "name_en": v[6] if v else key, "unit": s["unit"],
            "lat": s["lat"], "lon": s["lon"], "period": [s["y0"], s["y1"]], "available": s["available"],
            "reason": s.get("reason"), "reason_en": _reason_en(s.get("reason")), "live": s["live"],
            "source": s["source"], "source_en": s["source_en"],
            "giovanni_url": giovanni_url(key, s["lat"], s["lon"], s["y0"], s["y1"]) if v else None}
    if not s["available"]:
        return head
    return build_analysis(head, s)


def build_analysis(head: dict, s: dict) -> dict:
    """Ortak analiz gövdesi: head (key, name, name_en, unit, lat, lon, …) + seri s (dates, values, y0, y1, unit,
    lat, lon). Uydu ve gelgit verileri de (satellite.py) aynı şemayı bu fonksiyonla üretir."""
    try:
        a = analyze_values(s["values"], s["y0"], s["unit"], head["name"])
    except Exception as exc:
        return {**head, "available": False, "reason": f"analiz yapılamadı: {exc}"}
    ytr, yen = _yts_sentences(a)
    a["years_to_significance"].update({"sentence_tr": ytr, "sentence_en": yen})
    unit = s["unit"]
    dec, p = a["sen"]["per_decade"], a["mk"]["p"]
    fmt = (lambda x: f"{x:+.2g}") if abs(dec) < 0.01 else ((lambda x: f"{x:+.3f}") if abs(dec) < 0.1 else (lambda x: f"{x:+.2f}"))
    unit_tr = "birim (0–1 ölçeği)" if unit == "0–1" else unit
    unit_en = head.get("unit_en") or ("units (0–1 scale)" if unit == "0–1" else
                                      unit.replace("mm/ay", "mm/month").replace("gün", "day").replace("cm su", "cm water"))
    sig_tr = "anlamlı" if a["mk"]["significant"] else "anlamlı değil"
    sig_en = "significant" if a["mk"]["significant"] else "not significant"
    p_s = "p < 0,001" if p < 0.001 else f"p = {p:.3f}".replace(".", ",")
    p_e = "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
    pt = a['ttest']['p']
    pt_s = "< 0,001" if pt < 0.001 else "= " + f"{pt:.3f}".replace(".", ",")
    pt_e = "< 0.001" if pt < 0.001 else f"= {pt:.3f}"
    sentence_tr = (f"{head['name']} {s['y0']}–{s['y1']} arasında on yılda {fmt(dec).replace('.', ',')} {unit_tr} değişti "
                   f"(mevsimsel Mann-Kendall {p_s}, {sig_tr}; t-testi p {pt_s}).")
    sentence_en = (f"{head['name_en']} changed by {fmt(dec)} {unit_en} per decade over "
                   f"{s['y0']}–{s['y1']} (seasonal Mann-Kendall {p_e}, {sig_en}; t-test p {pt_e}).")
    if abs(dec) < 1e-12:   # Sen eğimi tam sıfır (ör. ayların çoğunda kar yok): "+0" yazmak yerine
        sentence_tr = (f"{head['name']} {s['y0']}–{s['y1']} arasında belirgin bir değişim göstermedi (Sen eğimi 0; "
                       f"mevsimsel Mann-Kendall {p_s}).")
        sentence_en = (f"{head['name_en']} showed no clear change over {s['y0']}–{s['y1']} (Sen slope 0; seasonal "
                       f"Mann-Kendall {p_e}).")
    yrs = a["annual"]["years"]
    xm, ym = float(np.median(np.arange(len(yrs)))), float(np.median(a["annual"]["values"]))
    sen_y = [round(ym + a["sen"]["per_year"] * (i - xm), 4) for i in range(len(yrs))]
    lo_y = [round(ym + a["sen"]["ci_low"] / 10 * (i - xm), 4) for i in range(len(yrs))]
    hi_y = [round(ym + a["sen"]["ci_high"] / 10 * (i - xm), 4) for i in range(len(yrs))]
    chart = {"metric": "variable", "kind": "line", "value": a["sen"]["per_year"], "unit": unit,
             "title_tr": f"{head['name']} · {_latlon(s['lat'], s['lon'], 'tr')}",
             "title_en": f"{head['name_en']} · {_latlon(s['lat'], s['lon'], 'en')}",
             "x_label_tr": "Yıl", "x_label_en": "Year", "y_label_tr": unit, "y_label_en": unit,
             "traces": [{"name_tr": "Aylık değer", "name_en": "Monthly value", "x": s["dates"],
                         "y": s["values"], "style": "line", "axis": "monthly"},
                        {"name_tr": "Yıllık ortalama", "name_en": "Annual mean", "x": yrs, "y": a["annual"]["values"],
                         "style": "marker"},
                        {"name_tr": "Sen doğrusu", "name_en": "Sen line", "x": yrs, "y": sen_y, "style": "line"}],
             "band": {"style": "band", "x": yrs, "y_low": lo_y, "y_high": hi_y,
                      "name_tr": "%95 güven aralığı", "name_en": "95% confidence interval"},
             "marks": [], "explain_tr": sentence_tr + " " + ytr, "explain_en": sentence_en + " " + yen}
    return {**head, **a, "chart": chart, "sentence_tr": sentence_tr, "sentence_en": sentence_en}


def trend_tests(region: str) -> dict | None:
    """Mevcut bölge tema serisi için aynı yöntem karşılaştırması (MK | t-testi | gereken yıl)."""
    from .config import START
    from .regions import REGIONS
    from .series import build_series

    if region not in REGIONS:
        return None
    try:
        spec = REGIONS[region]
        vals = build_series(region)[spec.variable].to_numpy(dtype=float).tolist()
        a = analyze_values(vals, int(START[:4]), spec.unit, spec.variable)
    except Exception:
        return None
    ytr, yen = _yts_sentences(a)
    a["years_to_significance"].update({"sentence_tr": ytr, "sentence_en": yen})
    a.pop("deseasonalized", None)
    return a


# ── Nokta tanımı ────────────────────────────────────────────────────────────
def _haversine(la1, lo1, la2, lo2) -> float:
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(min(1.0, h)))


def describe_point(lat: float, lon: float, end_year: int | None = None) -> dict:
    """Tıklanan nokta: {"lat", "lon", "nearest_region", "distance_km", "land" (bool|None), "elevation",
    "available_keys", "label_tr", "label_en", "ok"}. Veri çekme aynı önbellekli istekle yapılır."""
    from .regions import REGION_LIST

    lat = max(-89.5, min(89.5, float(lat)))
    lon = ((float(lon) + 180) % 360) - 180
    near = min(REGION_LIST, key=lambda r: _haversine(lat, lon, r.lat, r.lon))
    dist = _haversine(lat, lon, near.lat, near.lon)
    pd_ = point_data(lat, lon, end_year)
    land = None
    avail = []
    if pd_["ok"]:
        g = pd_["params"].get("GWETROOT", {})
        vals = [x for x in g.values() if x is not None]
        land = bool(vals) and sum(1 for x in vals if x > -900) > len(vals) * 0.5
        avail = [k for k in VARIABLES if variable_series(lat, lon, k, end_year)["available"]]
    lat_tr = f"{abs(lat):.1f}°{'K' if lat >= 0 else 'G'}".replace(".", ",")
    lon_tr = f"{abs(lon):.1f}°{'D' if lon >= 0 else 'B'}".replace(".", ",")
    lat_en = f"{abs(lat):.1f}°{'N' if lat >= 0 else 'S'}"
    lon_en = f"{abs(lon):.1f}°{'E' if lon >= 0 else 'W'}"
    km = f"{dist:,.0f}".replace(",", ".")
    return {"ok": pd_["ok"], "lat": round(lat, 2), "lon": round(lon, 2), "nearest_region": near.name,
            "distance_km": round(dist, 1), "land": land, "elevation": pd_["elev"], "available_keys": avail,
            "label_tr": f"{lat_tr} {lon_tr} · en yakın bölge {near.name} ({km} km)",
            "label_en": f"{lat_en} {lon_en} · nearest region {near.en[0] or near.name} ({dist:,.0f} km)",
            "error": pd_["error"]}
