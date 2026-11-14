# Data dictionary

All tables are under `db/`. CSV files are UTF-8 without a byte-order mark, comma separated, with
a header row and RFC 4180 quoting. Dates are `YYYY-MM-DD`, times are UTC as `YYYY-MM-DDTHH:MM`.
An empty cell means "not measured" or "does not apply"; a measured zero is written `0`.

Identifiers

- `volcano_id`: the target of the monitoring system. `GVP<number>` for a volcano of the
  Smithsonian's Global Volcanism Program, `CAL<n>` for a submarine caldera of the author's
  caldera list that has no GVP number, `IR-<name>` for a site taken from the InterRidge vents
  list.
- `zone_id`: `<volcano_id>-<letter>` for a high-resolution monitoring zone (`-A` the main zone,
  `-B`, `-C` further vents or cones, `-W` a wide zone round the whole edifice or caldera),
  `W-<volcano_id>` for the low-resolution zone. A trailing `-LS` in the pass tables marks a pass
  that was read on the Landsat grid of the same zone.
- `episode_id`: `<zone_id>_<YYYYMMDD of the first alert>`. An episode id can change when the
  screening rules change and the alerts of a zone are grouped anew.

## volcanoes.csv

One row per volcano (204).

| Column | Meaning |
|---|---|
| `volcano_id` | See above |
| `gvp_number` | Volcano number of the GVP, empty where there is none |
| `name`, `name_ja` | Name in English (GVP spelling where it has one) and, where established, in Japanese |
| `country` | Country as the GVP gives it |
| `lat`, `lon` | Position of the main zone centre, decimal degrees (WGS 84) |
| `depth_class` | Depth of the vent or summit: `lt200`, `200-500`, `500-1000` (metres), `near_surface` (vent near the sea surface), `near_surface_island` (land inside the caldera), `unknown` |
| `coverage` | High-resolution sensors that image the volcano: `s2+landsat`, `s2`, `landsat`, or `lowres_only` |
| `tiers` | `highres+lowres` or `lowres` |
| `baseline_class` | How alerts are decided: `quiet` (fixed thresholds), `frequent` or `persistent` (against the zone's own history) |
| `n_zones` | Number of high-resolution zones |
| `first_pass`, `last_pass` | First and last high-resolution pass in the database |
| `n_passes`, `n_usable` | High-resolution passes, and those with the sea visible (class A or B) |
| `lowres_days` | Days of the low-resolution record with the sea visible |
| `n_<class>` | Number of episodes of each class |
| `top_class` | The most significant class among the volcano's episodes |
| `last_activity` | End of the latest episode of class `known`, `likely` or `possible` |
| `summary_en`, `summary_ja` | Short summary of the record, written from the review reports |

## zones.csv

| Column | Meaning |
|---|---|
| `zone_id`, `volcano_id` | See above |
| `tier` | `highres` or `lowres` |
| `name` | Name of the zone (partly in Japanese) |
| `kind` | What the zone covers |
| `lat`, `lon`, `radius_km` | Centre and radius of the circle |
| `sensors` | `s2+landsat`, `s2`, `landsat` or `lowres` |

## episodes.csv

One row per episode. A high-resolution episode is a run of alert passes (level L2 or L3) of one
zone with no more than 21 days between neighbours; the passes of both sensors count together. A
low-resolution episode is a run of alert days of the survey in Sentinel-3 OLCI. Its numbers come
from that survey alone; the review of an episode also used the VIIRS and MODIS passes of the days
around it, and a review note or a volcano summary may give a larger area seen by those sensors.

| Column | Meaning |
|---|---|
| `episode_id`, `volcano_id`, `zone_id` | See above |
| `tier` | `highres` or `lowres` |
| `source` | `hindcast2` (hindcast of the archives, 2013-04 to 2025-11-11), `monitor` (the monitoring system's own store, from 2025-11-12), `olci_survey` (low-resolution survey, 2017-11 on) |
| `start`, `end` | First and last alert day |
| `n_detect` | High resolution: alert passes. Low resolution: days on which the largest patch of discoloured water lay within 5 km of the zone centre |
| `n_seen` | High resolution: usable passes between start and end. Low resolution: days with the sea visible |
| `n_l3` | Passes (days) of level L3 |
| `phenomena` | Reasons of the alerts, joined by `+`: `dw` discoloured water, `fl` floating matter, `nl` new land, `th` hot pixels, `sc` water colour of the whole zone, `ap` airborne band |
| `max_dw_km2` | Largest area of discoloured water on one pass (low resolution: on a day with the patch at the vent) |
| `max_fl_km2`, `max_nl_km2` | Largest area of floating matter and of new land |
| `colour` | Most frequent colour class of the discoloured water: `green`, `cyan`, `brown`, `white`, `none` |
| `median_dist_km` | Median distance of the centroid of the discoloured water from the zone centre (low resolution: smallest distance) |
| `sensors` | `Sentinel-2`, `Landsat`, `Landsat+Sentinel-2` or `OLCI` |
| `peak` | The strongest pass (as `<zone>_<YYYYMMDDTHHMM>_<satellite>`) or, at low resolution, the peak day |
| `class` | Public class, see below |
| `basis` | Where the class comes from: `catalogue` (date match with an eruption period), `ai_review` (AI-assisted review), `rule` (volcano with a usual feature), `lead_review` (conclusion of the review report), `owner` (the author's verdict) |
| `cause` | For `nonvolcanic`: `cloud`, `cloud_shadow`, `sun_glint`, `reef_or_shoal`, `land_or_surf`, `land_or_ice`, `bloom`, `sediment_plume`, `ship_wake`, `sensor_artifact`, `neighbour_eruption`, `other` |
| `interest` | Interest given by the first-pass review, 0 (dismissed) to 3; how much the episode deserved a second look, not a verdict |
| `known_ref` | The eruption period the episode was matched to: `GVP <kind> <start>..<end>` with the dates of the catalogue, or `Own event list <start>..<end>` |
| `prior_reports` | What was checked against earlier reports, with the date of the check. Empty: nothing was checked |
| `image` | Path of a review sheet under the image base (low-resolution episodes that were reviewed) |
| `note_en`, `note_ja` | Review note. Written in Japanese; the English is a translation and is missing for most dismissed episodes |
| `owner_en`, `owner_ja` | The author's verdict, where there is one |
| `curation_en`, `curation_ja` | Why the class was set by hand, where it was |

Classes

| `class` | Meaning |
|---|---|
| `known` | Overlaps a documented eruption period (GVP eruption table or the database's own event list), from 30 days before its start to 90 days after its end. Matched by date, not reviewed one by one |
| `likely` | Discoloured water, pumice or new land at the vent, judged likely volcanic |
| `possible` | Volcanic origin cannot be excluded, nothing decisive |
| `recurrent` | Pale water or turbidity that returns at the same place (eroding young island, shoal over the vent, hydrothermal bay). On record, not an alert |
| `airborne` | Faint band in the air beside an island; kind not decided |
| `undetermined` | Lowest interest, not looked at again |
| `nonvolcanic` | Dismissed, with a cause |
| `unreviewed` | Not reviewed |

## passes/&lt;volcano_id&gt;.csv

Every high-resolution pass over the zones of one volcano, alert or not, in order of time.

| Column | Meaning |
|---|---|
| `zone_id` | Zone; `-LS` marks the Landsat grid of the zone |
| `time` | Sensing time, UTC |
| `sat` | `S2A`, `S2B`, `S2C`, `L8`, `L9` |
| `cls` | Visibility of the sea surface in the zone: `A` (70 % or more clear), `B` (30 % or more), `C` (less; nothing was measured) |
| `clear` | Clear fraction of the zone |
| `level` | `L0` not visible, `L1` visible and no candidate, `L2` candidate, `L3` strong candidate |
| `reasons` | Reasons of an alert, as in `phenomena` |
| `dw_km2` | Area of candidate discoloured water, before the thresholds |
| `colour`, `dist_km`, `bearing` | Colour class of the discoloured water; distance (km) and bearing (degrees from north) of its centroid from the zone centre |
| `fl_km2`, `nl_km2` | Area of floating matter and of new land |
| `th_px` | Number of hot pixels |
| `ap_km2` | Area of an airborne band |
| `episode_id` | Episode the pass belongs to, for alert passes |
| `img` | `1` when the quicklook of the pass is published |

The quicklook of a pass is at
`<image base>/ql/<zone_id>/<zone_id>_<YYYYMMDDTHHMM>_<sat>.jpg`, with the image base given in
`meta.json` (`https://gis.ikgm.net/submvolc`). It is a JPEG of 640 by 320 pixels: true colour on
the left, the short-wave infrared composite on the right, the zone drawn as a circle, about 47 m
per pixel for most zones.

## lowres/&lt;volcano_id&gt;.csv

One row per day with the sea visible in the low-resolution zone (30 km radius).

| Column | Meaning |
|---|---|
| `date` | Day (UTC) |
| `src` | `olci` (Sentinel-3 OLCI, survey of the archive) or `viirs` (the monitor's daily VIIRS images) |
| `n_passes` | Passes of that day |
| `cls` | Best visibility class of the day, `A` or `B` |
| `level` | Level of the day, `L0` to `L3` |
| `dw_km2` | Area of water of a different colour, outside the zone's persistent mask |
| `bright_km2` | Area of bright floating matter |
| `dw_two_pass_km2` | Area flagged at the same place by two passes of the day |

These are screening values. Most low-resolution alerts are blooms, glacial turbidity, reefs or
cloud; only the episodes listed in `episodes.csv` were reviewed.

## known_periods.csv

Eruption periods since 2013 for the volcanoes of the database, as used for the class `known`.

| Column | Meaning |
|---|---|
| `volcano_id` | See above |
| `source` | `GVP` (Volcanoes of the World, Global Volcanism Program, Smithsonian Institution, retrieved 2026-11-11) or `monitor` (the database's own list of event periods, taken wide on purpose) |
| `kind` | `Confirmed Eruption`, `Uncertain Eruption` or `Event period` |
| `start`, `end` | Dates as given; a part that is not known is left out (`2014`, `2014-01`) |
| `continuing` | `yes` when the catalogue marked the eruption as continuing |
| `area`, `note` | Vent or area named by the catalogue; note of the own list |

## records/

- `ring_waves.csv`: passes on which the sea surface round a summit shows concentric wave crests.
  They are read as an effect of the seafloor relief on the swell and do not change a verdict.
- `airborne_bands.csv`: passes with a faint grey band in the air beside an island (Zubair Group).

## figures.csv

Figures shown on a volcano's page: `volcano_id`, `file` (path under the image base),
`caption_en`, `caption_ja`.

## index.json, meta.json

`index.json` is what the map page reads: the volcanoes with their episodes that are not dismissed,
as `[start, end, class index, tier index, phenomena]`. `meta.json` holds the build time, the commit
of the monitoring system the tables were built from, the image base and the counts.
