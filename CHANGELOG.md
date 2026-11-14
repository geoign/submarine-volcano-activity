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

- The author's first reviews in the form: 175 episodes, so that 200 are `human-reviewed`
  (3,557 `ai-reviewed`, 193 `automatic`). 104 of them changed class: 47 episodes without a review
  and 16 that the review had kept as possible or undetermined were judged not volcanic, 34 were
  raised to likely volcanic (most of them the recurring discoloured water of Fukutoku-Oka-no-Ba
  and Lateiki), two passes matched by date to the eruption of Snow volcano (Gorshkov Caldera)
  were judged to show the usual appearance of the place, and five moved to possible, undetermined
  or recurrent. Classes now: 89 known, 78 likely, 76 possible,
  234 recurrent, 22 airborne, 195 undetermined, 3,196 not volcanic, 60 unreviewed.
- Of the 22 episodes that disagreed with the Coast Guard's records, the author reviewed 19:
  four were raised to likely volcanic and one to possibly volcanic, one stays undetermined, and
  13 were confirmed as not volcanic. Three at Funka Asane are left.
- The summaries of 23 volcanoes say what the author judged; Napo Taroare has a summary.
  English text for the author's comments.
- Sofu-gan and the Sofu Seamount caldera are different volcanoes: the Coast Guard's table of
  Sofu-gan stays out of the database, and the data dictionary says so.
- The author's review form can leave out volcanoes where activity is seen almost all the time,
  takes the cause of a dismissal by key, shows all passes of an episode side by side and
  remembers the file it saves to.
