# Submarine Volcano Activity Database

A satellite record of shallow submarine volcanoes worldwide since 2013: discoloured water,
floating pumice, new land, thermal anomalies and bands in the air seen in Sentinel-2, Landsat and
low-resolution imagery, with the review of every detection.

- Site: <https://geoign.github.io/submarine-volcano-activity/>
- Methods, classes and limits: [docs/METHODS.en.md](docs/METHODS.en.md) ([日本語](docs/METHODS.ja.md))
- Data dictionary: [docs/DATA.md](docs/DATA.md)

This is not a volcano warning and not official volcano information. The reviews were made with
the help of AI (Claude, by Anthropic), and most records have not been checked by a person.

## What is here

| Path | Content |
|---|---|
| `db/` | The database: CSV tables and two JSON files |
| `index.html`, `volcano.html`, `episodes.html`, `about.html`, `assets/` | The site that shows it (static, no build step) |
| `curation/` | Hand-made inputs of the build: class overrides, volcano summaries, translations of the review notes, Japanese names, figure captions |
| `docs/` | Methods (English and Japanese) and the data dictionary |
| `tools/` | The tools that build `db/` from the stores of the monitoring system |
| `tests/` | Checks of the built tables |

The satellite images are not in this repository. The quicklook of every pass with the sea visible
is at `https://gis.ikgm.net/submvolc/ql/<zone>/<zone>_<time>_<satellite>.jpg` (see
[docs/DATA.md](docs/DATA.md)).

## Using the data

```python
import pandas as pd

episodes = pd.read_csv("https://raw.githubusercontent.com/geoign/submarine-volcano-activity/main/db/episodes.csv")
lateiki = pd.read_csv("https://raw.githubusercontent.com/geoign/submarine-volcano-activity/main/db/passes/GVP243070.csv")
print(episodes[episodes["class"].isin(["known", "likely", "possible"])].groupby("volcano_id").size())
print(lateiki[lateiki.level.isin(["L2", "L3"])][["time", "sat", "dw_km2", "colour"]])
```

## Looking at the site locally

```
python -m http.server 8765
```

and open <http://localhost:8765/>. The pages read `db/` with `fetch`, so they need a web server;
opening `index.html` from the file system does not work.

## Rebuilding the tables

The tables are built from the stores of the monitoring system, which is not part of this
repository. With that system checked out:

```
python tools/build_db.py --monitor D:/SubMVolc_Monitor   # db/
python tools/check_db.py                                 # counts, vocabularies, leaks
python tools/sync_images.py                              # new quicklooks to the image store
python tools/build_about.py                              # about.html from docs/METHODS.*.md
python tools/notes.py pending --out notes.csv            # review notes that lack an English text
```

`tools/build_db.py` only reads the monitor's stores. The class of an episode comes from the
monitor's reviews and from `curation/overrides.csv`; see the module docstrings.

## Sources

- Contains modified Copernicus Sentinel data (2015 to 2026): Sentinel-2 and Sentinel-3, obtained
  from Element 84's Earth Search and Microsoft's Planetary Computer.
- Landsat 8 and 9: U.S. Geological Survey, obtained from the Planetary Computer.
- VIIRS and MODIS images: NASA's Global Imagery Browse Services (GIBS).
- Eruption periods and volcano numbers: Volcanoes of the World, Global Volcanism Program,
  Smithsonian Institution (retrieved on 11 November 2026).
- Land outline of the map: Natural Earth. Map library: Leaflet (BSD 2-Clause, in
  `assets/vendor/leaflet/`).

## Licence and citation

The data (`db/`, `curation/`, the texts in `docs/` and the images) are under
[CC BY 4.0](LICENSE-DATA). The code (`tools/`, `tests/`, `assets/js/`, the style sheet and the HTML
pages) is under the [MIT licence](LICENSE). Leaflet, in `assets/vendor/leaflet/`, keeps its own
licence. The images are made from Copernicus Sentinel and Landsat data; give the sources above as
well when you reuse them.

> Ikegami, F. (2026). Submarine Volcano Activity Database.
> https://github.com/geoign/submarine-volcano-activity

Author: Fumihiko Ikegami (Ikegami GeoResearch), f.ikegami@gmail.com
