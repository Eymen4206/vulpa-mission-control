"""Dedektif ön izleme anlık görüntüsü (snapshots/regionvars.json): 50 bölge × 15 değişken, yıllık değerler.

Kullanım (proje kökünden):  .venv\\Scripts\\python -m data_pipelines.refresh_regionvars
3 paralel işçi ve artan bekleme (~1–3 dk). Her bölge noktası variables.py disk önbelleğine de yazılır.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

from .detective import load_regionvars, regionvars_annual
from .regions import REGION_LIST
from .trendgrid import annual_from_raw
from .variables import _point_raw, _snap, _window


def main() -> int:
    t0 = time.time()
    y0, y1 = _window(None)
    old = load_regionvars()
    old_regions = old.get("regions", {}) if old.get("years") == [y0, y1] else {}

    def work(r):
        la, lo = _snap(r.lat, r.lon)
        for attempt in range(6):
            try:
                return r.name, annual_from_raw(_point_raw(la, lo, y0, y1)["params"], y0, y1)
            except Exception:
                time.sleep(15 * (attempt + 1))
        return r.name, old_regions.get(r.name)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = dict(pool.map(work, REGION_LIST))
    missing = [n for n, v in results.items() if not v]
    if missing:
        print(f"{len(missing)} bölge alınamadı: {', '.join(missing)}; dosya yazılmadı.")
        return 1
    regionvars_annual(results, y0, y1)
    print(f"{len(results)} bölge yazıldı ({time.time() - t0:.0f} sn)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
