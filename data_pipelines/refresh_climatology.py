"""İklim normallerinin anlık görüntüsünü (snapshots/climatology.json) üretir: 50 bölge + 264 ızgara noktası.

Kullanım (proje kökünden):  .venv\\Scripts\\python -m data_pipelines.refresh_climatology
NASA POWER climatology uç noktası anahtarsızdır; ~314 istek paralel olarak ~1–2 dakikada tamamlanır.
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

from .climatology import fetch_point, load_climatology, write_climatology
from .config import GRID_LATS, GRID_LONS
from .regions import REGION_LIST


def _try(args):
    lat, lon = args
    for attempt in range(3):
        try:
            return fetch_point(lat, lon)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return None


def main() -> int:
    t0 = time.time()
    old = load_climatology()
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    jobs = [(r.lat, r.lon) for r in REGION_LIST] + list(zip(la.ravel().tolist(), lo.ravel().tolist()))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_try, jobs))
    regions, failed = {}, []
    for r, res in zip(REGION_LIST, results[:len(REGION_LIST)]):
        if res:
            regions[r.name] = res
        elif r.name in old.get("regions", {}):
            regions[r.name] = old["regions"][r.name]
        else:
            failed.append(r.name)
    grid = results[len(REGION_LIST):]
    old_grid = old.get("grid", [])
    grid = [g if g else (old_grid[i] if i < len(old_grid) else None) for i, g in enumerate(grid)]
    if any(g is None for g in grid):
        print(f"Izgara eksik: {sum(g is None for g in grid)} nokta alınamadı; dosya yazılmadı.")
        return 1
    path = write_climatology(regions, grid)
    print(f"{len(regions)}/50 bölge, {len(grid)} ızgara noktası → {path} ({time.time() - t0:.0f} sn)")
    if failed:
        print("Başarısız bölgeler:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
