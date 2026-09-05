# Does `recipe-scrapers` cover the sites the household cooks from?

Type: research
Status: open
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
