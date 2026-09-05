# Does `recipe-scrapers` cover the sites the household cooks from?

Type: research
Status: resolved
Blocked by: —
Parent: ../map.md

## Question

The entry track is URL import, and `features.md` already specs it around the
`recipe-scrapers` library. Before committing the track, establish what that
dependency actually buys:

1. **Coverage.** How many sites are supported, where the authoritative list
   lives, and how someone checks one specific site in under a minute.
2. **Wild mode.** The spec's fallback for unsupported sites
   (`scrape_preview(html, url, wild_mode=True)`). What does it actually return
   on a site with no dedicated scraper — usable structured ingredients, or
   mush? This determines how much ticket 06 matters.
3. **Maintenance health.** Release cadence, open-issue posture, Python version
   support, license, transitive dependency weight.
4. **Breakage model.** Sites change their markup. How often do scrapers break
   in practice, and what does a household deployment do when one does?
5. **Alternatives.** Anything better for a self-hosted, offline-by-default,
   no-LLM app. Note the standing constraint in `features.md`: **no LLM or
   hosted AI dependency.** Also check whether schema.org `Recipe`
   microdata/JSON-LD alone would cover most sites without the library.

### Not answerable here

Which specific sites the household cooks from — the owner hasn't listed them.
Report the coverage picture and the one-minute check so that list can be
resolved against it later.

### Answer records

Findings file plus a recommendation: adopt `recipe-scrapers`, adopt it with a
JSON-LD fallback, or something else.

## Answer

Findings: [`../research/recipe-scrapers.md`](../research/recipe-scrapers.md).

**Adopt `recipe-scrapers` as specced (option a), with three spec amendments.**

- **Coverage.** 725 domains in 15.12.0. Authoritative list is `SCRAPERS` in the
  package itself (docs page is generated from it). One-minute check:
  `scraper_exists_for(url)`, offline.
- **Wild mode is good, and "supported" barely matters.** Measured on the
  library's 1109 real-page fixtures: the generic schema.org path finds a recipe
  on 91.1%, gives usable ingredients on 87.7%, ≥90% line-recall on 80.3%.
  Near-misses are cosmetic (`3/4` vs `¾`), not mush. 50% of the 625 scrapers
  override nothing — they are 7-line host registrations behaving identically to
  wild mode.
- **The failure path is narrow and sharply shaped.** Live: 4/4 unsupported food
  blogs worked; 6/6 Substack posts and 1 bespoke CMS returned
  `NoSchemaFoundInWildMode` (no Recipe markup at all); 2/20 fetches hit
  Cloudflare 403. So ticket 06's fallback is for newsletters and bot-protected
  sites, not for routine blogs — and bot protection is as common as missing schema.
- **Health.** MIT, Python 3.10–3.14, 256 PRs merged in 12 months, but 78% of
  commits by one person. +20 packages / ~23 MB (12 MB is `lxml`).
- **Breakage.** ~8% of scrapers repaired per year; CI is offline so breaks are
  found by users. Pin in `uv.lock`; add a 5-line retry on the library's own
  `SchemaScraperFactory` when a dedicated scraper returns empty.
- **JSON-LD-only (option c) is a false economy.** Hand-rolled graph-aware
  JSON-LD: 83.6% ingredients / 59.6% exact vs the library's 87.7% / 75.9%, and
  8.1% vs 83.9% on microdata sites. Peers agree: Mealie and Tandoor both pin
  this library and call `supported_only=False`.
- **Spec amendments** (`features.md` § URL import): `wild_mode=` is deprecated →
  `supported_only=False`; the two-pass normal-then-wild retry is unnecessary
  (one call does both); every field accessor can raise, so `scrape_preview` must
  `try/except` per field — partial results are the normal shape, not an edge case.
