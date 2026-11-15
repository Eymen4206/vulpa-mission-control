# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""Ek ölçüm veri setlerinin anlık görüntüsünü üretir (snapshots/extra_series.json).

Kullanım (proje kökünden):  .venv\\Scripts\\python -m data_pipelines.refresh_extra SEAICE_N [GPM ...]
Earthdata gerektiren veri setleri `.streamlit/secrets.toml` içindeki [earthdata] token'ını kullanır (yalnızca bu
betik; uygulama token kullanmaz).
"""

from __future__ import annotations

import io
import sys
import time

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import pandas as pd
import requests

from .satellite import DATASETS, write_extra
from .variables import _window

SEAICE_URL = "https://noaadata.apps.nsidc.org/NOAA/G02135/{hemi}/monthly/data/{H}_{mm:02d}_extent_v4.0.csv"


def _monthly_list(series: pd.Series, y0: int, y1: int) -> list:
    idx = pd.date_range(f"{y0}-01-01", f"{y1}-12-01", freq="MS")
    s = series.groupby(series.index.to_period("M").to_timestamp()).mean().reindex(idx)
    return [None if pd.isna(v) else round(float(v), 4) for v in s]


def seaice_north(y0: int, y1: int) -> dict:
    rows = {}
    for mm in range(1, 13):
        resp = requests.get(SEAICE_URL.format(hemi="north", H="N", mm=mm), timeout=60)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), skipinitialspace=True)
        df.columns = [c.strip() for c in df.columns]
        for y, m, ext in zip(df["year"], df["mo"], df["extent"]):
            if float(ext) > 0:
                rows[pd.Timestamp(int(y), int(m), 1)] = float(ext)
    vals = _monthly_list(pd.Series(rows).sort_index(), y0, y1)
    return {r: vals for r in DATASETS["SEAICE_N"]["regions"]}


# ── Earthdata (GES DISC OPeNDAP) ────────────────────────────────────────────
def _earthdata_session() -> requests.Session:
    import tomllib
    from pathlib import Path
    sec = tomllib.loads((Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {sec['earthdata']['token']}"
    return s


def _parse_dap_ascii(text: str, var: str) -> list[list[float]]:
    """OPeNDAP .ascii çıktısındaki `var[0][i], v, v, …` satırlarını 2B listeye çevirir."""
    rows = []
    for line in text.splitlines():
        if line.startswith(var + "["):
            parts = line.split(",")
            rows.append([float(x) for x in parts[1:]])
    return rows


def _grid_points():
    import numpy as np
    from .config import GRID_LATS, GRID_LONS
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    return list(zip(la.ravel().tolist(), lo.ravel().tolist()))


def _sample_1deg(field, lat0: float, lon0: float, lat: float, lon: float):
    """1° alandan (field[lon_i][lat_j], merkezler lon0 + i, lat0 + j) en yakın hücre."""
    i = int(round(((lon + 180) % 360 - 180 - lon0))) % len(field)
    j = min(max(int(round(lat - lat0)), 0), len(field[0]) - 1)
    v = field[i][j]
    return None if v is None or v < -9000 else v


def gpm_imerg(y0: int, y1: int) -> dict:
    """GPM IMERG V07 aylık (0,1°) → 1° adımla örneklenmiş küresel alan; her ay tek istek. mm/saat → mm/ay.
    Ay dosyaları cache/ altına yazılır; yarıda kalırsa kaldığı yerden devam eder."""
    import calendar
    import json as _json
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from .regions import REGION_LIST

    cache = Path(__file__).with_name("cache") / "gpm"
    cache.mkdir(parents=True, exist_ok=True)
    sess = _earthdata_session()
    base = "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/GPM_3IMERGM.07"
    months = [(y, m) for y in range(y0, y1 + 1) for m in range(1, 13)]
    done = [0]
    t0 = time.time()

    def one(ym):
        y, m = ym
        f = cache / f"{y}{m:02d}.json"
        if f.exists():
            return ym, _json.loads(f.read_text())
        url = (f"{base}/{y}/3B-MO.MS.MRG.3IMERG.{y}{m:02d}01-S000000-E235959.{m:02d}.V07B.HDF5.ascii"
               "?precipitation[0][5:10:3599][5:10:1799]")
        for attempt in range(5):
            try:
                r = sess.get(url, timeout=180)
                r.raise_for_status()
                field = _parse_dap_ascii(r.text, "precipitation")
                if len(field) != 360 or len(field[0]) != 180:
                    raise ValueError(f"beklenmeyen boyut {len(field)}×{len(field[0]) if field else 0}")
                f.write_text(_json.dumps(field))
                break
            except Exception as exc:  # noqa: BLE001
                err = exc
                time.sleep(10 * (attempt + 1))
        else:
            print(f"  ✗ {y}-{m:02d}: {err}", flush=True)
            return ym, None
        done[0] += 1
        if done[0] % 12 == 0:
            print(f"  {done[0]} ay indirildi ({time.time() - t0:.0f} sn)", flush=True)
        return ym, field

    with ThreadPoolExecutor(max_workers=3) as pool:
        fields = dict(pool.map(one, months))
    pts = [(r.name, r.lat, r.lon) for r in REGION_LIST]
    regions = {name: [] for name, _, _ in pts}
    grid = [[] for _ in _grid_points()]
    for (y, m) in months:
        fld = fields.get((y, m))
        hours = 24 * calendar.monthrange(y, m)[1]
        for name, la, lo in pts:
            v = _sample_1deg(fld, -89.45, -179.45, la, lo) if fld else None
            regions[name].append(None if v is None else round(v * hours, 2))
        for k, (la, lo) in enumerate(_grid_points()):
            v = _sample_1deg(fld, -89.45, -179.45, la, lo) if fld else None
            grid[k].append(None if v is None else round(v * hours, 2))
    return {"regions": regions, "grid": grid}


# ── PSMSL gelgit ölçerleri (anahtarsız) ─────────────────────────────────────
PSMSL_STATIONS = {   # bölge → (PSMSL kimliği, istasyon adı, bölge merkezine uzaklık km)
    "ABD Doğu Kıyısı": (2324, "Lewisetta, Virginia", 41),
    "Florida Everglades": (1858, "Virginia Key, Florida", 74),
    "Chao Phraya Deltası": (444, "Fort Phrachula Chomklao (Bangkok)", 6),
    "Yangtze Deltası": (934, "Kanmen", 347),
}
PSMSL_PERIOD = (2000, 2024)   # 2025 verisi henüz tüm istasyonlarda yayımlanmadı


def psmsl(y0: int, y1: int) -> dict:
    y0, y1 = PSMSL_PERIOD
    out, meta = {}, {}
    for region, (sid, name, km) in PSMSL_STATIONS.items():
        r = requests.get(f"https://psmsl.org/data/obtaining/rlr.monthly.data/{sid}.rlrdata", timeout=60)
        r.raise_for_status()
        vals = {}
        for line in r.text.splitlines():
            p = [x.strip() for x in line.split(";")]
            t, v = float(p[0]), int(p[1])
            y, m = int(t), int(round((t - int(t)) * 12 + 0.5))
            if v != -99999:
                vals[(y, m)] = v
        out[region] = [vals.get((y, m)) for y in range(y0, y1 + 1) for m in range(1, 13)]
        meta[region] = {"station": name, "psmsl_id": sid, "distance_km": km}
    return {"regions": out, "grid": None, "period": PSMSL_PERIOD, "meta": meta}


# ── Earthdata Cloud OPeNDAP (GES DISC) — genel dilim çekici ─────────────────
CLOUD_OPENDAP = "https://opendap.earthdata.nasa.gov/collections/{cid}/granules/{gid}.dap.csv?dap4.ce={ce}"


def _cmr_granules(short_name: str, version: str, t0: str, t1: str) -> list[tuple[str, str, str]]:
    """[(collection_id, granule_title, start_date)] — CMR anahtarsız."""
    out, page = [], 1
    while True:
        r = requests.get("https://cmr.earthdata.nasa.gov/search/granules.json", params={
            "short_name": short_name, "version": version, "temporal": f"{t0},{t1}", "page_size": 2000,
            "page_num": page, "sort_key": "start_date"}, timeout=120)
        r.raise_for_status()
        e = r.json()["feed"]["entry"]
        if not e:
            break
        out += [(x["collection_concept_id"], x["title"], x["time_start"][:10]) for x in e]
        page += 1
    return out


def _parse_dap4_csv(text: str) -> dict[str, list[list[float]]]:
    """dap.csv çıktısı: '/Var[0][j], v, v, …' satırları → {Var: [[…], …]} (satır = ilk uzaysal boyut)."""
    out: dict[str, list] = {}
    for line in text.splitlines():
        if not line.startswith("/"):
            continue
        head, _, rest = line.partition(",")
        name = head.split("[")[0].split("/")[-1]
        out.setdefault(name, []).append([float(x) for x in rest.split(",") if x.strip()])
    return out


def _cloud_fetch(sess, cid: str, gid: str, ce: str, cache_file) -> dict | None:
    import json as _json
    from urllib.parse import quote
    if cache_file.exists():
        return _json.loads(cache_file.read_text())
    url = CLOUD_OPENDAP.format(cid=cid, gid=quote(gid, safe=""), ce=ce)
    err = None
    for attempt in range(5):
        try:
            r = sess.get(url, timeout=180)
            r.raise_for_status()
            data = _parse_dap4_csv(r.text)
            if not data:
                raise ValueError("boş yanıt")
            cache_file.write_text(_json.dumps(data))
            return data
        except Exception as exc:  # noqa: BLE001
            err = exc
            time.sleep(8 * (attempt + 1))
    print(f"  ✗ {gid}: {err}", flush=True)
    return None


def _sample_rows_lat(field, lat0: float, lon0: float, step: float, lat: float, lon: float):
    """field[lat_j][lon_i] (satır = enlem), merkezler lat0 + j·step, lon0 + i·step; en yakın hücre, −9999 → None."""
    if not field:
        return None
    j = int(round((lat - lat0) / step))
    i = int(round((((lon + 180) % 360) - 180 - lon0) / step)) % len(field[0])
    ok = lambda v: v is not None and v > -9000 and v == v  # noqa: E731
    if 0 <= j < len(field) and ok(field[j][i]):
        return field[j][i]
    # Kıyı: hücre denizdeyse en yakın geçerli komşu (önce 1, sonra 2 hücre halkası)
    for r in (1, 2):
        best = None
        for dj in range(-r, r + 1):
            for di in range(-r, r + 1):
                jj, ii = j + dj, (i + di) % len(field[0])
                if 0 <= jj < len(field) and ok(field[jj][ii]):
                    dist = dj * dj + di * di
                    if best is None or dist < best[0]:
                        best = (dist, field[jj][ii])
        if best:
            return best[1]
    return None


def _collect(items: dict, sampler, transforms: dict, months: list, regions_list, grid_pts) -> dict:
    """items: {(y, m): veri sözlüğü}; transforms: {dataset_key: f(veri, (y, m), lat, lon) -> değer|None}."""
    res = {}
    for key, fn in transforms.items():
        regs = {r.name: [] for r in regions_list}
        grid = [[] for _ in grid_pts]
        for ym in months:
            d = items.get(ym)
            for r in regions_list:
                regs[r.name].append(fn(d, ym, r.lat, r.lon) if d else None)
            for k, (la, lo) in enumerate(grid_pts):
                grid[k].append(fn(d, ym, la, lo) if d else None)
        res[key] = {"regions": regs, "grid": grid}
    return res


def gldas(y0: int, y1: int) -> dict:
    """GLDAS-2.1 Noah aylık (0,25°) → 1° dilim. Tek istekte 4 alan: yüzey akışı, taban akışı, 100–200 cm toprak nemi,
    kar su eşdeğeri. Çıktı: GLDAS_RUNOFF (mm/ay), GLDAS_SOILDEEP (kg/m² = mm), GLDAS_SWE (mm)."""
    import calendar
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from .regions import REGION_LIST

    cache = Path(__file__).with_name("cache") / "gldas"
    cache.mkdir(parents=True, exist_ok=True)
    sess = _earthdata_session()
    grans = _cmr_granules("GLDAS_NOAH025_M", "2.1", f"{y0}-01-01T00:00:00Z", f"{y1}-12-31T23:59:59Z")
    sl = "[0][2:4:599][2:4:1439]"
    ce = ";".join(f"/{v}{sl}" for v in ("Qs_acc", "Qsb_acc", "SoilMoi100_200cm_inst", "SWE_inst"))
    done = [0]

    def one(g):
        cid, gid, start = g
        y, m = int(start[:4]), int(start[5:7])
        d = _cloud_fetch(sess, cid, gid, ce, cache / f"{y}{m:02d}.json")
        done[0] += 1
        if done[0] % 24 == 0:
            print(f"  GLDAS {done[0]}/{len(grans)}", flush=True)
        return (y, m), d

    with ThreadPoolExecutor(max_workers=3) as pool:
        items = dict(pool.map(one, grans))
    months = [(y, m) for y in range(y0, y1 + 1) for m in range(1, 13)]
    smp = lambda f, la, lo: _sample_rows_lat(f, -59.375, -179.375, 1.0, la, lo)  # noqa: E731

    def runoff(d, ym, la, lo):
        a, b = smp(d.get("Qs_acc"), la, lo), smp(d.get("Qsb_acc"), la, lo)
        if a is None or b is None:
            return None
        return round((a + b) * 8 * calendar.monthrange(*ym)[1], 2)   # 3 saatlik birikim ortalaması → aylık toplam

    res = _collect(items, smp, {
        "GLDAS_RUNOFF": runoff,
        "GLDAS_SOILDEEP": lambda d, ym, la, lo: (lambda v: None if v is None else round(v, 2))(
            smp(d.get("SoilMoi100_200cm_inst"), la, lo)),
        "GLDAS_SWE": lambda d, ym, la, lo: (lambda v: None if v is None else round(v, 2))(smp(d.get("SWE_inst"), la, lo)),
    }, months, REGION_LIST, _grid_points())
    return {"multi": res}


def airs(y0: int, y1: int) -> dict:
    """AIRS v7 aylık L3 (1°, gündüz geçişi) → 2° dilim. Sıcaklık: 850 / 300 / 70 hPa; toplam ozon (Dobson).
    AIRS Eylül 2002'de başlar; 2001–Ağustos 2002 boştur (%7, analiz eşiğinin altında)."""
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from .regions import REGION_LIST

    cache = Path(__file__).with_name("cache") / "airs"
    cache.mkdir(parents=True, exist_ok=True)
    sess = _earthdata_session()
    grans = _cmr_granules("AIRS3STM", "7.0", f"{y0}-01-01T00:00:00Z", f"{y1}-12-31T23:59:59Z")
    ce = ("/ascending/Data_Fields/Temperature_A[2:5:12][0:2:179][0:2:359];"
          "/ascending/Data_Fields/TotO3_A[0:2:179][0:2:359]")
    done = [0]

    def one(g):
        cid, gid, start = g
        y, m = int(start[:4]), int(start[5:7])
        d = _cloud_fetch(sess, cid, gid, ce, cache / f"{y}{m:02d}.json")
        done[0] += 1
        if done[0] % 24 == 0:
            print(f"  AIRS {done[0]}/{len(grans)}", flush=True)
        return (y, m), d

    with ThreadPoolExecutor(max_workers=3) as pool:
        raw = dict(pool.map(one, grans))
    # Satırlar kuzeyden güneye (89,5 → −89,5); güneyden kuzeye çevir. Sıcaklıkta 3 seviye × 90 satır.
    items = {}
    for ym, d in raw.items():
        if not d:
            continue
        t = d.get("Temperature_A") or []
        o = d.get("TotO3_A") or []
        n = len(o) or 90
        items[ym] = {"T850": t[0:n][::-1], "T300": t[n:2 * n][::-1], "T70": t[2 * n:3 * n][::-1], "O3": o[::-1]}
    months = [(y, m) for y in range(y0, y1 + 1) for m in range(1, 13)]
    smp = lambda f, la, lo: _sample_rows_lat(f, -89.5, -179.5, 2.0, la, lo)  # noqa: E731
    k2c = lambda v: None if v is None else round(v - 273.15, 2)  # noqa: E731
    res = _collect(items, smp, {
        "AIRS_T850": lambda d, ym, la, lo: k2c(smp(d.get("T850"), la, lo)),
        "AIRS_T300": lambda d, ym, la, lo: k2c(smp(d.get("T300"), la, lo)),
        "AIRS_T70": lambda d, ym, la, lo: k2c(smp(d.get("T70"), la, lo)),
        "AIRS_O3": lambda d, ym, la, lo: (lambda v: None if v is None else round(v, 1))(smp(d.get("O3"), la, lo)),
    }, months, REGION_LIST, _grid_points())
    return {"multi": res}


OMI_PERIOD = (2005, 2024)   # OMI Ekim 2004'te başladı


def omi_no2(y0: int, y1: int) -> dict:
    """OMI/Aura OMNO2d (günlük, 0,25°) troposferik NO₂ (bulut elemeli). Her ay 4 gün (1, 8, 15, 22) örneklenir,
    1° dilimden aylık ortalama alınır (en az 2 geçerli gün). Birim: 10¹⁵ molekül/cm². Dönem 2005–2024."""
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from .regions import REGION_LIST

    y0, y1 = OMI_PERIOD
    cache = Path(__file__).with_name("cache") / "omi"
    cache.mkdir(parents=True, exist_ok=True)
    sess = _earthdata_session()
    grans = _cmr_granules("OMNO2d", "003", f"{y0}-01-01T00:00:00Z", f"{y1}-12-31T23:59:59Z")
    pick = [g for g in grans if int(g[2][8:10]) in (1, 8, 15, 22)]
    ce = "/HDFEOS/GRIDS/ColumnAmountNO2/Data_Fields/ColumnAmountNO2TropCloudScreened[2:4:719][2:4:1439]"
    done = [0]

    def one(g):
        cid, gid, start = g
        d = _cloud_fetch(sess, cid, gid, ce, cache / f"{start.replace('-', '')}.json")
        done[0] += 1
        if done[0] % 48 == 0:
            print(f"  OMI {done[0]}/{len(pick)}", flush=True)
        return start, (d or {}).get("ColumnAmountNO2TropCloudScreened")

    with ThreadPoolExecutor(max_workers=3) as pool:
        days = dict(pool.map(one, pick))
    by_month: dict = {}
    for start, f in days.items():
        if f:
            by_month.setdefault((int(start[:4]), int(start[5:7])), []).append(f)
    months = [(y, m) for y in range(y0, y1 + 1) for m in range(1, 13)]
    smp = lambda f, la, lo: _sample_rows_lat(f, -89.375, -179.375, 1.0, la, lo)  # noqa: E731

    def no2(fields, ym, la, lo):
        vals = [v for v in (smp(f, la, lo) for f in fields) if v is not None and v > -1e29]
        return round(sum(vals) / len(vals) / 1e15, 3) if len(vals) >= 2 else None

    res = _collect(by_month, smp, {"OMI_NO2": no2}, months, REGION_LIST, _grid_points())
    res["OMI_NO2"]["period"] = OMI_PERIOD
    return {"multi": res}


def modis_ndvi(y0: int, y1: int) -> dict:
    """MODIS Terra MOD13C2 v061 aylık NDVI (0,05° CMG) → 1° dilim. Ölçek 1/10000; −3000 = boş (deniz/kar)."""
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from .regions import REGION_LIST

    cache = Path(__file__).with_name("cache") / "modis"
    cache.mkdir(parents=True, exist_ok=True)
    sess = _earthdata_session()
    grans = _cmr_granules("MOD13C2", "061", f"{y0}-01-01T00:00:00Z", f"{y1}-12-31T23:59:59Z")
    ce = "/MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_NDVI[10:20:3599][10:20:7199]"
    done = [0]

    def one(g):
        cid, gid, start = g
        y, m = int(start[:4]), int(start[5:7])
        d = _cloud_fetch(sess, cid, gid, ce, cache / f"{y}{m:02d}.json")
        done[0] += 1
        if done[0] % 24 == 0:
            print(f"  MODIS {done[0]}/{len(grans)}", flush=True)
        return (y, m), (d or {}).get("CMG_0_05_Deg_Monthly_NDVI")

    with ThreadPoolExecutor(max_workers=3) as pool:
        raw = dict(pool.map(one, grans))
    items = {ym: {"NDVI": [[(v / 10000.0 if v > -2000 else -9999.0) for v in row] for row in f[::-1]]}
             for ym, f in raw.items() if f}
    months = [(y, m) for y in range(y0, y1 + 1) for m in range(1, 13)]
    smp = lambda f, la, lo: _sample_rows_lat(f, -89.525, -179.475, 1.0, la, lo)  # noqa: E731
    res = _collect(items, smp, {
        "MODIS_NDVI": lambda d, ym, la, lo: (lambda v: None if v is None else round(v, 4))(smp(d.get("NDVI"), la, lo)),
    }, months, REGION_LIST, _grid_points())
    return {"multi": res}


GRACE_PERIOD = (2003, 2024)   # GRACE Nisan 2002'de başladı; 2017-07 – 2018-05 GRACE→GRACE-FO boşluğu (%4)
GRACE_URL = ("https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-protected/TELLUS_GRAC-GRFO_MASCON_CRI_GRID_"
             "RL06.3_V4/GRCTellus.JPL.200204_202609.GLO.RL06.3M.MSCNv04CRI.nc")


def _pyfive():
    """pyfive (saf Python HDF5 okuyucu). Python 3.15'te numcodecs/fsspec derlenemediği için, yalnızca bu betik
    sürecinde, kullanılmayan iki yardımcıyı en küçük yer tutucularla tanımlar (Fletcher32 doğrulaması ve uzak dosya
    toplu okuması; yerel ve filtresiz GRACE dosyasında ikisi de çağrılmaz)."""
    import struct
    import types
    import importlib.util
    if importlib.util.find_spec("numcodecs") is None:
        nc = types.ModuleType("numcodecs")

        class Fletcher32:
            def encode(self, buf):
                data = bytes(buf) + (b"\x00" if len(buf) % 2 else b"")
                s1 = s2 = 0
                for (w,) in struct.iter_unpack("<H", data):
                    s1 = (s1 + w) % 65535
                    s2 = (s2 + s1) % 65535
                return bytes(buf) + struct.pack(">HH", s2, s1)
        nc.Fletcher32 = Fletcher32
        sys.modules["numcodecs"] = nc
    if importlib.util.find_spec("fsspec") is None:
        fs, fu = types.ModuleType("fsspec"), types.ModuleType("fsspec.utils")

        def merge_offset_ranges(*a, **k):
            raise RuntimeError("fsspec toplu okuma bu betikte yok")
        fu.merge_offset_ranges = merge_offset_ranges
        fs.utils = fu
        sys.modules["fsspec"], sys.modules["fsspec.utils"] = fs, fu
    import pyfive
    return pyfive


def grace(y0: int, y1: int) -> dict:
    """JPL GRACE/GRACE-FO mascon RL06.3 CRI (0,5° ızgara, ~3° mascon): toplam su depolaması anomalisi (cm su eşdeğeri,
    2004–2009 ortalamasına göre). Tek dosya (46 MB) bir kez indirilir; bölge ve ızgara noktalarının sütunları okunur."""
    import datetime as _dt
    from pathlib import Path
    from .regions import REGION_LIST

    y0, y1 = GRACE_PERIOD
    f = Path(__file__).with_name("cache") / "grace" / GRACE_URL.rsplit("/", 1)[1]
    f.parent.mkdir(parents=True, exist_ok=True)
    if not f.exists():
        r = _earthdata_session().get(GRACE_URL, stream=True, timeout=300)
        r.raise_for_status()
        with open(f, "wb") as out:
            for ch in r.iter_content(1 << 20):
                out.write(ch)
    h = _pyfive().File(str(f))
    days = [float(x) for x in h["time"][:]]
    ym = [(d.year, d.month) for d in (_dt.datetime(2002, 1, 1) + _dt.timedelta(days=x) for x in days)]
    lwe = h["lwe_thickness"]
    months = [(y, m) for y in range(y0, y1 + 1) for m in range(1, 13)]

    def column(lat, lon):
        j = min(max(int(round((lat + 89.75) / 0.5)), 0), 359)
        i = int(round(((lon % 360) - 0.25) / 0.5)) % 720
        col = [float(v) for v in lwe[:, j, i]]
        acc: dict = {}
        for k, v in zip(ym, col):
            if v > -9000:
                acc.setdefault(k, []).append(v)
        return [round(sum(acc[k]) / len(acc[k]), 2) if k in acc else None for k in months]

    regions = {r.name: column(r.lat, r.lon) for r in REGION_LIST}
    grid = [column(la, lo) for la, lo in _grid_points()]
    return {"multi": {"GRACE_TWS": {"regions": regions, "grid": grid, "period": GRACE_PERIOD}}}


FETCHERS = {"SEAICE_N": seaice_north, "GPM": gpm_imerg, "SEALEVEL": psmsl, "GLDAS": gldas, "AIRS": airs,
            "OMI": omi_no2, "MODIS": modis_ndvi, "GRACE": grace}


def main(keys: list[str]) -> int:
    y0, y1 = _window(None)
    rc = 0
    for key in keys:
        t0 = time.time()
        try:
            regions = FETCHERS[key](y0, y1)
        except Exception as exc:  # noqa: BLE001
            print(f"✗ {key}: {type(exc).__name__}: {exc}")
            rc = 1
            continue
        if isinstance(regions, dict) and "multi" in regions:      # tek indirmeden birden fazla veri seti
            for sub, payload in regions["multi"].items():
                path = write_extra(sub, tuple(payload.get("period") or (y0, y1)), payload["regions"], payload["grid"],
                                   None)
                miss = sum(1 for vals in payload["regions"].values() if sum(v is None for v in vals) > len(vals) * 0.1)
                print(f"✓ {sub}: {len(payload['regions'])} bölge (eksik >%10: {miss}) → {path}")
            print(f"  ({time.time() - t0:.0f} sn)")
            continue
        grid, period, meta = None, (y0, y1), None
        if isinstance(regions, dict) and "regions" in regions and "grid" in regions:
            period = tuple(regions.get("period") or (y0, y1))
            meta = regions.get("meta")
            regions, grid = regions["regions"], regions["grid"]
        path = write_extra(key, period, regions, grid, meta)
        miss = sum(1 for vals in regions.values() if sum(v is None for v in vals) > len(vals) * 0.1)
        print(f"✓ {key}: {len(regions)} bölge (eksik >%10: {miss}), ızgara: {len(grid) if grid else 0} "
              f"→ {path} ({time.time() - t0:.0f} sn)")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or list(FETCHERS)))
