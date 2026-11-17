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

## 2026-11-14, third update

- The author's first reviews in the form: 218 episodes, so that 243 are `human-reviewed`
  (3,517 `ai-reviewed`, 190 `automatic`). 140 of them changed class: 49 episodes without a review
  and 49 that the review had kept as possible or undetermined were judged not volcanic, 33 were
  raised to likely volcanic (most of them the recurring discoloured water of Fukutoku-Oka-no-Ba
  and Lateiki), three passes matched by date to a documented eruption (two at Gorshkov Caldera,
  one at Myojinsho) were judged not volcanic, and six moved to possible, undetermined or
  recurrent. Classes now: 88 known, 77 likely, 77 possible, 234 recurrent, 22 airborne,
  161 undetermined, 3,232 not volcanic, 59 unreviewed.
- A review can be withdrawn (`curation/review_withdrawn.csv`). The author withdrew the review of
  the episode of 2017-04-08 at Napo Taroare the same day, until it is settled whether the pale
  patch there is discoloured water or the shoal at the zone centre; the episode awaits review.
- Of the 22 episodes that disagreed with the Coast Guard's records, the author reviewed 19:
  four were raised to likely volcanic and one to possibly volcanic, one stays undetermined, and
  13 were confirmed as not volcanic. Three at Funka Asane are left.
- The summaries of 24 volcanoes say what the author judged; Napo Taroare and Doyo Seamount have a summary.
  English text for the author's comments.
- Sofu-gan and the Sofu Seamount caldera are different volcanoes: the Coast Guard's table of
  Sofu-gan stays out of the database, and the data dictionary says so.
- The author's review form can leave out volcanoes where activity is seen almost all the time,
  takes the cause of a dismissal by key, shows all passes of an episode side by side and
  remembers the file it saves to.

## 2026-11-17

- Passes up to 2026-11-16 (the monitoring cycle of 2026-11-17).
- 11 zones on earthquake clusters (`kind` "zone on an earthquake cluster (centroid of the
  epicentres)"), so 408 zones. They hold 25 episodes: six matched to a known eruption or event
  period (Kavachi, Titan Ridge), one of this cycle judged not volcanic (Kolumbo), 18 without a
  review.
- The second hindcast was built again after a review of the monitoring system's code: 24,987 of its
  passes had been judged against the current land mask and reference image although a baseline of
  their own period existed; the 1,980 of them whose images are still stored were judged again, and
  the store was levelled with the current zone table (the six volcanoes treated as having a usual
  feature since 2026-11-14 among them). Hindcast episodes: 3,435 (3,488); 76 episodes are gone and
  23 new ones are parts of earlier episodes whose alert passes changed (St. Andrew Strait, Tagoro,
  Moekeshiwan, Zubair group, Raoul Island, Kuril 45.43N, Panarea), all without a review.
- A review counts only for the alert days it was given on: a verdict carried from the first hindcast
  for the days of the first hindcast's episode, a verdict of the second hindcast for the days of the
  episode as it was then (`curation/hindcast2_triaged_days.csv`, the list of 2026-11-14). 81 reviews
  are set aside, about as many as before by the same rule for carried verdicts; the only episode
  that loses its review is that of Tagoro of 2024-10-04, now a single pass. Episodes with alert days
  their review did not see are `ai_review_partial`.
- The Smithsonian catalogue is read with its end dates as given: an eruption without an end date is
  no longer taken as going on, and one marked `>` before its end year was still going on at the last
  date the catalogue gives (Kavachi from 2020, '>' 2024-04-24, now shown as "..continuing"). So one
  episode of Kavachi of 2024-08-31 that the review had kept as possibly volcanic is known, the
  episodes of Kavachi from 2024-08 to 2026-10 refer to that eruption (the author's verdicts on them
  stand), the summary of Kavachi says so, and the episode of the Zubair group of 2014-01-27 refers
  to the eruption that built Jadid Island (the three of 2013 did already). The episode of Kaitoku
  Seamount of 2023-03-31 refers to the monitoring system's own event period (2022-08-15 to
  2023-03-31) instead of the Smithsonian eruption.
- Judged against its own period's baseline, the "new land" detection of Fukutoku-Oka-no-Ba of
  2024-04-30, which the first hindcast had found false, is no longer an alert, and its override is
  gone with its episode. Likewise the first pass of the author's reviewed episode of Tagoro of
  2016-05-07 is no longer an alert; the review stays in `curation/human_review.csv`, and the
  remaining pass (episode of 2016-05-23) awaits the author's review. The author's reviewed episode
  of the Zubair group of 2024-03-15 (airborne) took in the next episode (2024-05-09 to 06-07,
  recurrent by the rule for places with a usual feature) and now holds 8 alert passes instead of 2;
  the verdict stays and is to be checked by the author.
- The low-resolution daily record was judged again: 2,515 Sentinel-3A passes of 2023-04-26 to 05-10
  had been stored as "no data" (bad catalogue footprints); the slice of 2023-04-26 to 07-25 was
  fetched again (1,212 passes read, 401 days added), and every day was levelled again (4,383 days
  changed, 1,253 in level: 739 from L2 to L1, 233 from L1 to L2, 230 from L3 to L2, 51 others). Two
  days of Kuiwai (2026-10-26, 10-27) are out since its passes, whose window crosses the
  antimeridian, were fetched again as one overpass each. The low-resolution episodes are still those
  reviewed on 2026-11-14.
- Classes now: 95 known, 77 likely, 76 possible, 214 recurrent, 22 airborne, 161 undetermined, 3,180
  not volcanic, 100 unreviewed; 242 `human-reviewed`, 3,445 `ai-reviewed`, 238 `automatic`.
