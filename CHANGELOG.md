# Changelog

Changes of the data and of the way it is built. Routine additions of new passes are not listed
one by one; `db/meta.json` says when the tables were built and up to which pass.

## 2026-11-14

First publication.

- 204 volcanoes, 397 monitoring zones.
- High-resolution passes from 2013-04-01 to 2026-11-12 (Sentinel-2, Landsat 8 and 9): the second
  hindcast of the archives up to 2025-11-11, the monitoring system's own store after that.
- Low-resolution daily record from 2017-11 (Sentinel-3 OLCI survey).
- Episodes with their public class, the review notes in Japanese, and English translations of
  the notes of all episodes that were not dismissed.
- Quicklooks of every pass with the sea visible at `https://gis.ikgm.net/submvolc/ql/`.

## 2026-11-14, second update

- Every episode has a review status (`review_status`, `reviewed_at`): 30 are `human-reviewed`
  (cases the author had judged before), 3,665 `ai-reviewed`, 255 `automatic`. The author's reviews
  are entered in a local form and kept in `curation/human_review.csv`.
- Observations by aircraft and ship from the Japan Coast Guard's database of submarine volcanoes
  for 14 volcanoes of Japan: `db/jcg_observations.csv`, 714 rows from 2013-01-22 to 2026-09-17,
  215 of them with something seen. For the 244 episodes at these volcanoes, `prior_reports` says
  what that database has within 14 days. The classes are unchanged: 22 episodes that the review
  had dismissed, left undetermined or counted as a usual feature have a record of something seen
  in their zone at the time, and wait for the author's review.
