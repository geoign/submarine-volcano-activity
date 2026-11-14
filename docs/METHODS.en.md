# Methods and data

## This database

This database records what public satellite imagery has shown at shallow submarine volcanoes around the world since 2013: discoloured water, floating matter such as pumice, new land, thermal anomalies and bands in the air.
It covers 204 volcanoes. Every satellite pass is screened by the same rules, and every pass that raises an alert is reviewed.

The record up to November 2025 comes from a hindcast through the image archives.
Later records come from the monitoring system and are updated whenever the monitoring runs.
The monitoring is built to run twice a week; as of November 2026 the routine runs have not yet begun.

This is not a volcano warning and not official volcano information.
The reviews were made with the help of AI (Claude, by Anthropic), and most records have not been checked by a person.
Please read the section "Limits" below before you use the data.

## Targets and monitoring zones

The targets are submarine volcanoes whose summit or vent is shallow enough for activity to show at the sea surface, submarine vents around volcanic islands, and submarine calderas.
The author chose them from the volcano list of the Smithsonian's Global Volcanism Program (GVP) and from the literature.

Each volcano has monitoring zones.
A high-resolution zone is a circle of 2 to 20 km radius around a summit, a vent or a caldera; there are 193 of them at 169 volcanoes.
The low-resolution zone is one circle of 30 km radius per volcano.
Sentinel-2 and Landsat do not image 35 of the volcanoes, which are watched in low-resolution imagery only.

## Imagery

| Tier | Sensors | Pixel | Period in the database |
|---|---|---|---|
| High resolution | Sentinel-2 (L2A), Landsat 8 and 9 (Collection 2 Level-2) | 20 to 40 m (Landsat 30 m) | from April 2013 |
| Low resolution | Sentinel-3 OLCI (300 m), daily VIIRS images (250 m); MODIS is also used to check candidates | 250 to 300 m | from November 2017 |

## Screening

For every pass the first decision is whether the sea surface was visible.
If 70 % or more of the pixels of the zone's circle are neither cloud nor cloud shadow the pass is class A, with 30 % or more class B, with less class C.
A pass of class C counts as "not seen", never as "nothing there".

On a pass with the sea visible the following are measured.

- Discoloured water. Sun glint is estimated from the short-wave infrared and taken off; then the pixels are sought whose visible light is brighter than the ordinary water of the same image. A pixel is a candidate when it meets one of three rules: brightness, a green or brown colour, or the difference between green and red. Patches smaller than 0.02 km², patches that touch cloud, edges of cloud shadow, and pixels that are candidates at that zone all the time (reefs and shoals) are left out. The area, the distance and bearing from the zone centre, and the colour (brown, green, cyan, white) are recorded.
- Floating matter. Pixels where red is stronger than blue, near infrared weaker than red and short-wave infrared weaker still are counted as pumice.
- New land. Counted when pixels with the spectrum of land appear three times in a row at the same place away from the known coast.
- Hot pixels. Counted from two short-wave infrared bands. They never raise an alert alone; they raise the level of an alert that has another reason.
- Airborne band. A long, narrow grey band that is slightly and equally bright in every band from blue to 2.2 µm. Bands beside land or beside the zone centre are counted.
- Water colour of the zone. Recorded when the water of the whole zone is greener than the zone's own past.

A pass has one of four levels.

| Level | Meaning |
|---|---|
| L0 | The sea surface was not visible |
| L1 | The sea surface was visible and there was no candidate |
| L2 | Discoloured water, floating matter, new land or an airborne band passed its threshold |
| L3 | Discoloured water of 1 km² or more and three times the threshold or more, or several reasons at once |

The threshold for discoloured water is 0.05 km². It is raised on passes with the sea only partly visible, on passes with sun glint, for white candidates and for Landsat.
At volcanoes where something always shows, such as reefs, shoals or a young island that is being eroded, a pass raises an alert only when it exceeds the zone's own past.

In the low-resolution tier the areas of water of a different colour and of bright floating matter are measured in the daily image of each volcano, against the open ocean of the same image.
The bars in the lower panel of a timeline are these daily values; they have not been reviewed one by one.

## Episodes

An episode is a run of alert passes (L2 or L3) of one zone with no more than 21 days between neighbours.
In the low-resolution survey it is a run of alert days.
Of the low-resolution episodes, the list holds only those reviewed from the images, where discoloured water lay within 5 km of the zone centre on two days or more, and those that overlap a documented eruption period.

## Review

The review had three stages.

1. First pass. AI assistants looked at a review figure for each episode (the alert pass, the usual appearance, a close-up, the short-wave infrared composite, the passes before and after) and either dismissed it with a cause such as cloud or sun glint, or flagged it for a second look with an interest from 1 to 3.
2. Second look. A lead AI reviewer went through the flagged episodes volcano by volcano in order of time and wrote reports.
3. The author's verdict. The author, a volcanologist, read the reports and judged some of the cases himself.

The field "Basis" of an episode says which stage its class comes from.
"The owner" in the review notes means the author of this database.

## Classes

| Class | Meaning |
|---|---|
| Documented eruption period | The episode overlaps a period in the GVP eruption table or in this database's own list of events. Matched by date only, not looked at one by one |
| Likely volcanic | Discoloured water, pumice or new land at the position of the vent that the reviewers judged likely to be volcanic |
| Possibly volcanic | A volcanic origin cannot be excluded, but nothing is decisive |
| Recurrent discolouration | Pale water or turbidity that returns at the same place, as at a young island being eroded, a shoal over the vent or a bay with hydrothermal activity. Kept on record; not an alert |
| Airborne band | A faint band in the air beside an island. Whether it is thin cloud, dust or a fumarolic plume is not decided |
| Undetermined | A candidate of the lowest interest that was not looked at again |
| Not volcanic | Dismissed as cloud, sun glint, reef, bloom, a fault of the product and so on |
| Not reviewed | Not yet reviewed |

Discoloured water outlasts an eruption, so the match to a documented eruption period takes the period from 30 days before the start of the eruption to 90 days after its end.

For activity outside the documented eruption periods, the field "Earlier reports checked" says what was checked.
Where that field is empty, earlier reports were not checked.
A record in this database does not mean that the activity had not been reported.

## Limits

- This is not real-time monitoring. Sentinel-2 revisits a zone every 2 to 5 days, and the screening and the review come after that.
- About half of all passes show the sea surface. A zone under persistent cloud has gaps of weeks in its record.
- Small activity, pale discoloured water and deep eruptions that leave nothing at the sea surface are not in the record. Nor is discoloured water under thick cloud or under an eruption plume. White steam cannot be told from cloud, nor volcanic ash from dust.
- The thresholds are provisional. In six known events labelled by eye, 46 of the 64 days on which a phenomenon was visible raised an alert; in the four events judged with fixed thresholds, 39 of 43 days.
- A volcano with frequent activity is judged against its own past, so the onset of its next activity can be passed over as "the usual range".
- A low-resolution pixel is 250 to 300 m, and small activity does not show. Most candidates come from blooms at high latitudes, glacial turbidity, reefs and the eruptions of neighbouring volcanoes, and only a part has been reviewed. From July 2023 to February 2026 the archive that was used holds only about a quarter of the Sentinel-3 OLCI passes.
- Landsat takes more sun glint than Sentinel-2, and a larger share of its alerts was dismissed. A part of the Landsat passes of 2022 could not be read.
- An AI review both overlooks and misreads. An area is the sum of the pixels the rules took as candidates, not a calibrated measurement.

## Data

The tables are in `db/` of the GitHub repository, as CSV (UTF-8) and JSON. All times are UTC.

| File | Content |
|---|---|
| `volcanoes.csv`, `zones.csv` | The volcanoes and their monitoring zones |
| `episodes.csv` | Every episode with its class, basis and review note (Japanese and English) |
| `passes/<volcano>.csv` | Every high-resolution pass, including the passes without an alert and those with the sea not visible |
| `lowres/<volcano>.csv` | The daily low-resolution record (days with the sea visible) |
| `known_periods.csv` | The eruption periods used for the matching |
| `records/` | Records of concentric ring waves and of airborne bands |

The fields are described in `docs/DATA.md` of the repository.

For every pass with the sea visible there is a JPEG image of 640 by 320 pixels.
The left half is true colour, the right half the short-wave infrared composite, and the circle is the monitoring zone.
The address is `https://gis.ikgm.net/submvolc/ql/<zone>/<zone>_<time>_<satellite>.jpg`.

## Sources

- Sentinel-2 and Sentinel-3: contains modified Copernicus Sentinel data (2015 to 2026), obtained from Element 84's Earth Search and Microsoft's Planetary Computer.
- Landsat 8 and 9: data of the U.S. Geological Survey (USGS), obtained from the Planetary Computer.
- VIIRS and MODIS images: NASA's Global Imagery Browse Services (GIBS).
- Eruption periods and volcano numbers: Volcanoes of the World, Global Volcanism Program, Smithsonian Institution (retrieved on 11 November 2026).
- The land on the map is from Natural Earth; the map is drawn with Leaflet.

## Terms of use and citation

The data (the tables in `db/` and the images) are under CC BY 4.0; the code is under the MIT licence.
The images are made from Copernicus Sentinel and Landsat data, so please also give the sources above when you reuse them.

An example of a citation:

Ikegami, F. (2026). Submarine Volcano Activity Database. https://github.com/geoign/submarine-volcano-activity

The author is Fumihiko Ikegami (Ikegami GeoResearch). Contact: f.ikegami@gmail.com
