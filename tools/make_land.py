"""Write assets/land.json, the land outline of the overview map, from Natural Earth 1:50m.

    python tools/make_land.py <path to>/ne_50m_land.shp

Natural Earth is in the public domain (naturalearthdata.com). The polygons are simplified and
rounded to 0.01 degree; the file is a list of polygons, each a list of rings of [lon, lat].
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd

TOLERANCE = 0.03
OUT = Path(__file__).resolve().parents[1] / "assets" / "land.json"


def main(src: str) -> None:
    gdf = gpd.read_file(src)
    polys = []
    for geom in gdf.geometry:
        geom = geom.simplify(TOLERANCE, preserve_topology=True)
        for g in getattr(geom, "geoms", [geom]):
            if g.is_empty or g.area < 0.002:
                continue
            rings = [[[round(x, 2), round(y, 2)] for x, y in g.exterior.coords]]
            rings += [[[round(x, 2), round(y, 2)] for x, y in r.coords] for r in g.interiors if len(r.coords) > 8]
            polys.append(rings)
    OUT.write_text(json.dumps(polys, separators=(",", ":")), encoding="utf-8", newline="\n")
    n = sum(len(r) for p in polys for r in p)
    print(f"{OUT}: {len(polys)} polygons, {n} points, {OUT.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main(sys.argv[1])
