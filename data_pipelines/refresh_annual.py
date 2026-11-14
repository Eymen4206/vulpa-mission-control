"""Sene ortalaması anlık görüntüsünü (snapshots/annual.json) üretir: 50 bölge + 264 ızgara noktası, 1991–son yıl.

Kullanım (proje kökünden):  .venv\\Scripts\\python -m data_pipelines.refresh_annual
NASA POWER yoğun isteklerde 429 döndürdüğü için az sayıda paralel işçi ve artan bekleme kullanılır (~3–8 dk).
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

import numpy as np

from .annual import fetch_with_retry, load_annual, write_annual
from .config import GRID_LATS, GRID_LONS
from .regions import REGION_LIST


def main() -> int:
    t0 = time.time()
    old = load_annual()
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    jobs = [(r.lat, r.lon) for r in REGION_LIST] + list(zip(la.ravel().tolist(), lo.ravel().tolist()))
    done = [0]

    def work(args):
        res = fetch_with_retry(*args)
        done[0] += 1
        if done[0] % 25 == 0:
            print(f"  {done[0]}/{len(jobs)} ({time.time() - t0:.0f} sn)", flush=True)
        return res

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(work, jobs))
    regions, failed = {}, []
    for r, res in zip(REGION_LIST, results[:len(REGION_LIST)]):
        if res:
            regions[r.name] = res
        elif r.name in old.get("regions", {}):
            regions[r.name] = old["regions"][r.name]
        else:
            failed.append(r.name)
    old_grid = old.get("grid", [])
    grid = [g if g else (old_grid[i] if i < len(old_grid) else None) for i, g in enumerate(results[len(REGION_LIST):])]
    missing = sum(g is None for g in grid)
    if missing:
        print(f"Izgarada {missing} nokta alınamadı; dosya yazılmadı. Biraz sonra tekrar çalıştırın.")
        return 1
    path = write_annual(regions, grid)
    print(f"{len(regions)}/50 bölge, {len(grid)} ızgara noktası → {path} ({time.time() - t0:.0f} sn)")
    if failed:
        print("Başarısız bölgeler:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
