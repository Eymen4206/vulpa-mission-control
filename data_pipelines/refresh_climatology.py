# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""İklim normallerinin anlık görüntüsünü (snapshots/climatology.json) üretir: tüm bölgeler + 264 ızgara noktası.

Kullanım (proje kökünden):  .venv\\Scripts\\python -m data_pipelines.refresh_climatology   (yalnızca yeni bölgeler: --new)
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
    # --new: yalnızca anlık görüntüde olmayan bölgeler çekilir; mevcut bölgeler ve ızgara aynen korunur
    only_new = "--new" in sys.argv and len(old.get("grid", [])) == la.size
    targets = [r for r in REGION_LIST if not (only_new and r.name in old.get("regions", {}))]
    jobs = [(r.lat, r.lon) for r in targets] + ([] if only_new else list(zip(la.ravel().tolist(), lo.ravel().tolist())))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_try, jobs))
    regions, failed = {}, []
    kept = {r.name: old["regions"][r.name] for r in REGION_LIST if only_new and r.name in old.get("regions", {})}
    regions.update(kept)
    for r, res in zip(targets, results[:len(targets)]):
        if res:
            regions[r.name] = res
        elif r.name in old.get("regions", {}):
            regions[r.name] = old["regions"][r.name]
        else:
            failed.append(r.name)
    grid = (results[len(targets):] if not only_new else old['grid'])
    old_grid = old.get("grid", [])
    grid = [g if g else (old_grid[i] if i < len(old_grid) else None) for i, g in enumerate(grid)]
    if any(g is None for g in grid):
        print(f"Izgara eksik: {sum(g is None for g in grid)} nokta alınamadı; dosya yazılmadı.")
        return 1
    path = write_climatology(regions, grid)
    print(f"{len(regions)}/{len(REGION_LIST)} bölge, {len(grid)} ızgara noktası → {path} ({time.time() - t0:.0f} sn)")
    if failed:
        print("Başarısız bölgeler:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
