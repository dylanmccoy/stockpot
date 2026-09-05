# Is `recipe-scrapers` a good bet for URL import?

Research findings for [ticket 02](../issues/02-recipe-scrapers-coverage.md) ·
verified **2026-09-05** against `recipe-scrapers` **15.12.0** (released
2026-08-08) and repo `main` @ `d08ddd0` (2026-08-21).

## Verdict up front

**Adopt it — option (a), with three spec amendments.** Option (b)'s JSON-LD
fallback is measurably redundant (the library's own generic path beats a
hand-rolled JSON-LD parser on every metric), and option (c) is a downgrade that
loses ~5.6% of sites outright and degrades line quality on the rest.

| Question | Answer |
|---|---|
| Coverage | 725 domains in 15.12.0; authoritative list is `SCRAPERS` in the package's `__init__.py`, published at docs.recipe-scrapers.com |
| Wild mode | Real. Full structured output on **~91%** of real recipe pages, nothing at all on ~12%. It is *not* mush — near-misses are cosmetic |
| Maintenance | Healthy: 263 commits / 256 merged PRs in 12 months, MIT, Python 3.10–3.14. One caveat: **bus factor 1** (78% of commits by one person) |
| Breakage | ~48 targeted scraper repairs/year across 625 scrapers ≈ **8%/yr per scraper**. CI is offline-only, so breakage is found by users, not by tests |
| Weight | **+20 packages, ~23 MB** installed (12 MB of it `lxml`). All permissive licenses |
| Alternatives | None better under the no-LLM constraint. Both leading self-hosted peers (Mealie, Tandoor) pin this exact library |

## How the numbers were produced

Two experiments, both reproducible offline:

1. **Fixture corpus** — the library's own regression suite: **1109 real saved
   HTML pages across 640 hosts** (`tests/test_data/`, each with a maintainer-
   authored expected-output `.json`). For every fixture I ran (a) the generic
   schema.org path — i.e. exactly what an *unsupported* site gets — and (b) two
   hand-rolled JSON-LD parsers, and scored both against the expected output
   that the *dedicated* scraper produces.
2. **Live sample** — 20 recipe URLs fetched fresh on 2026-09-05, 13 of them on
   hosts with **no** dedicated scraper.

Bias note: corpus hosts all *have* a scraper, so they skew toward sites someone
cared about. That cuts both ways — 84 of them have a scraper precisely
*because* generic parsing fails there, which inflates the failure rate rather
than hiding it.

---

## 1. Coverage

| Fact | Value | Source |
|---|---|---|
| Domains supported | **725** | `len(SCRAPERS)` in installed 15.12.0 |
| Distinct scraper classes | 624 (636 modules) | `recipe_scrapers/__init__.py` |
| Docs site count | 739 (tracks `main`, ahead of the release) | https://docs.recipe-scrapers.com/getting-started/supported-sites/ |
| TLD spread | 479 `.com`, 72 `.es`, 22 `.de`, 14 `.nl`, 12 `.uk`, 10 `.au`, 9 each `.fr`/`.it`/`.se` | computed from `SCRAPERS` keys |

**Authoritative list lives in the code**, not in a data file: the docs page is
generated at build time by executing `from recipe_scrapers import SCRAPERS`
(see `docs/getting-started/supported-sites.md` — it is a `python exec="on"`
block). So the installed package is always the ground truth; the website can
lag or lead it.

**Fastest check for one site** (offline, no network, sub-second):

```python
from recipe_scrapers import scraper_exists_for
scraper_exists_for("https://www.kitchensanctuary.com/chicken-traybake/")  # True
```

**Better check for the household's actual list** — answers the question that
matters, which is not "supported?" but "will import work?":

```python
# pip install recipe-scrapers ; then feed it the household's URLs
import warnings; warnings.filterwarnings("ignore")
import urllib.request
from recipe_scrapers import scrape_html, scraper_exists_for, NoSchemaFoundInWildMode

UA = {"User-Agent": "Mozilla/5.0"}
for url in URLS:
    try:
        html = urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read().decode("utf-8", "replace")
    except Exception as e:
        print("FETCH-BLOCKED", url, e); continue          # bot protection lives here
    try:
        s = scrape_html(html, org_url=url, supported_only=False)
    except NoSchemaFoundInWildMode:
        print("NO-SCHEMA    ", url); continue             # hard fail: needs the paste path
    print("dedicated" if scraper_exists_for(url) else "generic  ",
          len(s.ingredients()), "ingredients,", len(s.instructions_list()), "steps —", url)
```

Three outcomes, not two: **dedicated**, **generic** (works fine), and the two
real failures — **NO-SCHEMA** and **FETCH-BLOCKED**.

### "Supported" is a much weaker signal than the spec assumes

**314 of the 625 scraper modules (50%) override no fields at all.** They exist
only to register a hostname; everything is done by the same schema.org fill
plugin that serves the generic path. Median scraper module is **13 lines**.
`allrecipes.py` in full:

```python
from ._abstract import AbstractScraper

class AllRecipes(AbstractScraper):
    @classmethod
    def host(cls):
        return "allrecipes.com"
```

Consequence for the UI and for ticket 06: for half of "supported" sites,
dedicated and wild mode are *behaviourally identical*. Labelling a site
"unsupported" tells the user almost nothing about whether import will work.

---

## 2. Wild mode — the decision-relevant item

### What it actually does

`recipe_scrapers/_schemaorg.py` runs `extruct.extract(..., syntaxes=["json-ld",
"microdata"], uniform=True)` and then, over both syntaxes:

- traverses `@graph` arrays and `WebPage.mainEntity` to find the `Recipe` node;
- dereferences `Person` / `AggregateRating` nodes by `@id` for author + rating;
- recurses `HowToSection` → `itemListElement` → `HowToStep` for instructions,
  de-duplicating the common `name`-is-a-truncated-`text` pattern;
- handles `recipeIngredient` as string, list, list-of-lists, or schema.org
  `PropertyValue` (`value` + `unitText` + `name`);
- parses ISO-8601 durations *and* `QuantitativeValue.maxValue`, sums
  `prepTime + cookTime` when `totalTime` is absent;
- normalises yields, strips HTML tags, normalises whitespace, picks the best
  image, and falls back to OpenGraph — all via the plugin chain in
  `settings/default.py`.

That is ~1070 lines of accumulated edge-case handling (`_schemaorg.py` 409 +
`_utils.py` 429 + `_grouping_utils.py` 231).

### What it returns on an unsupported site

| Outcome | Object / exception |
|---|---|
| Schema found | `SchemaScraperFactory.SchemaScraper` — `title`, `ingredients`, `ingredient_groups`, `instructions`, `instructions_list`, `yields`, `total_time`, `cook_time`, `prep_time`, `image`, `author`, `category`, `cuisine`, `description`, `ratings`, `canonical_url` |
| No schema found | raises **`NoSchemaFoundInWildMode`** |
| Supported-only mode, unknown host | raises **`WebsiteNotImplementedError`** |

Both exceptions map cleanly onto the spec's `422 unsupported: true`.

### How reliable — 1109 real pages

Generic path only (no dedicated scraper), scored against what the dedicated
scraper produces:

| Metric | Result |
|---|---|
| Page exposes a parseable schema.org `Recipe` | **1010 / 1109 (91.1%)** — 948 JSON-LD, 62 microdata |
| Title matches the dedicated scraper exactly | 998 / 1109 (90.0%) |
| Ingredients non-empty | 973 / 1109 (87.7%) |
| Ingredients **byte-identical** to the dedicated scraper | 842 / 1109 (75.9%) |
| Ingredients ≥90% line-recall | **890 / 1109 (80.3%)** |
| Instructions non-empty | 961 / 1109 (86.7%) |
| Ingredients empty | 136 / 1109 (12.3%) |
| Non-empty but unusable (one blob / wrong list) | 38 / 1109 (3.4%) |

Per host: **77 / 640 (12.0%)** hosts where the generic path yields nothing on
every fixture; **506 / 640 (79.1%)** where every fixture is ≥90% recall.

### Not mush — the near-misses are cosmetic

Every case in the `0 < recall < 0.9` band (45 fixtures) is a formatting
difference a human would accept in a preview box and edit in seconds:

- `¾ cup all purpose flour` (dedicated) vs `3/4 cup all purpose flour` (generic)
- `3 tablespoons butter, divided` vs `3 tablespoons butter, (divided)`
- group headers folded into the list: `For the panna cotta:` as an ingredient
- occasional truncation of a long trailing descriptor

The genuinely bad 3.4% has one recognisable shape: the site put its whole
ingredient list into a **single JSON-LD string**, so you get one 14-line blob
instead of 14 lines (barefootcontessa.com, eatwell101.com, cookingcircle.com).
Still readable by a human; not structured. Splitting that blob is exactly what
those sites' dedicated scrapers exist to do.

### Live check on 13 genuinely unsupported hosts

| Class | Result |
|---|---|
| Recipe-plugin blogs (WPRM / Tasty Recipes) — `healthylivingjames.co.uk`, `carriecarvalho.com`, `veggiedesserts.com`, `justapinch.com` | **4/4 perfect.** 9–17 ingredients, 5–7 steps, yields and total time present |
| Substack newsletters ×6 | **0/6.** `NoSchemaFoundInWildMode` — Substack emits `NewsArticle` + `BreadcrumbList` only, no `Recipe` node anywhere |
| `rickstein.com` (bespoke CMS) | **0/1.** One ld+json block, no `Recipe` type |
| Bot protection — `kitchensanctuary.com`, `saveur.com` (both *supported* sites) | **HTTP 403 Cloudflare interstitial.** Fetch fails before parsing is even reached |

The failure population is sharply defined: **prose/newsletter sites with no
recipe plugin, and sites behind bot protection.** Neither is fixable by any
parser — including a hand-rolled one, including (were it permitted) an LLM
without the page content. Both need the human paste path.

**Implication for ticket 06:** the fallback still matters, but not as a
routine path — expect it on newsletter-style sources and Cloudflare-fronted
sites, not on ordinary food blogs. And 2/20 live fetches were blocked, which
makes bot protection at least as common a failure as missing schema.

---

## 3. Maintenance health

| Signal | Value |
|---|---|
| Latest release | 15.12.0, **2026-08-08** (226 releases since 5.0.0 in 2019) |
| Recent cadence | 15.9.0 Aug-25 · 15.10.0 Nov-25 · 15.11.0 Dec-25 · 15.12.0 Aug-26 — an **8-month release gap** in 2026, though `main` kept moving (134 commits Mar–Aug 2026) |
| Commits, last 12 mo | 263 (604 over 24 mo) |
| PRs merged, last 12 mo | **256** (150 since 2026-01-01) |
| Open issues / PRs | 104 issues (26 `bug`, 56 `enhancement`, 10 `bots-protection`) · 29 PRs, only 6 older than a year |
| Stale backlog | 40 open issues older than 2 years; 12 open `bug` issues older than 18 months. 622 issues closed lifetime |
| Repo | 2 221 ★, 671 forks, created 2015, last push 2026-08-21, not archived |
| Python | `requires-python >=3.10`; classifiers and CI cover **3.10–3.14** (backend needs ≥3.12 — fine) |
| CI | GitHub Actions, 3 OS × 5 Python versions, runs all 1109 fixtures |
| License | **MIT** (package and repo). Every transitive dep is permissive: MIT / BSD-3 / Apache-2.0 / MPL-2.0 / W3C / PSF |

**The one real risk is concentration.** Of 263 commits in the last 12 months,
**206 (78%) are by a single contributor**; the next-highest is 7. If that
person stops, the release cadence stops. Mitigations are cheap: the library is
MIT, pure Python, and the whole value is a dict of hostnames plus ~1000 lines
of schema parsing — forkable in an afternoon if it ever came to that.

### Dependency weight

Installing it into this backend adds **20 packages** and **~23 MB**:

`beautifulsoup4` · `soupsieve` · `extruct` · `lxml` (12 MB) · `lxml-html-clean`
· `rdflib` (2.6 MB) · `pyrdfa3` · `mf2py` · `w3lib` · `html-text` · `html5lib`
· `webencodings` · `jstyleson` · `isodate` · `pyparsing` · `six` · `requests` ·
`urllib3` · `charset-normalizer` · `certifi`

For reference the backend's current lock is 37 packages total, so this roughly
doubles it. Notes:

- `lxml` is a compiled wheel — fine on WSL/Linux x86-64, but it is the one
  thing in the tree that is not pure Python.
- `rdflib` + `pyrdfa3` + `mf2py` (~3 MB, plus they are why `requests` appears)
  are pulled by `extruct` for RDFa and microformats **syntaxes the library
  never requests** — `_schemaorg.py` asks only for `json-ld` and `microdata`.
  Dead weight, unavoidable while `extruct` has no extras. (The docs index page
  claims RDFa support; the code does not use it.)
- Do **not** install the `[online]` extra — the spec's `fetch_bytes` owns the
  network, and the library is explicitly HTML-parsing-only.

---

## 4. Breakage model

**Measured rate:** over the last 12 months of `main`, ignoring the 3 bulk
refactor commits, there were **48 commits that repaired 1–3 existing scrapers
and added none**, against 625 scrapers. That is roughly **8% of scrapers
repaired per year**. For a household with ~10 favourite sites, expect on the
order of **one break per year**. Three scrapers were deleted outright in that
window (`cookscountry.py`, `cooksillustrated.py`, `leanandgreenrecipes.py`) —
sites that went away or went behind a paywall.

Representative repair commits: *"fix: bbcgoodfood.com scraper (#2015)"*,
*"update simplehomeedit to work with updated website (#2010)"*, *"Fix:
halfbakedharvest.com instruction list parsing (#1887)"*.

**How breakage is detected: by users, not by the library.** CI runs entirely
against saved HTML fixtures with `online=False`. A site changing its markup
cannot turn CI red — it turns *your* import red, and someone has to open an
issue. The 26 open `bug` issues are that queue.

**The library's story for it**, in order of what a household deployment would
actually do:

1. **Pin and update deliberately.** Every version is on PyPI; `uv.lock` already
   pins transitively. Mealie pins `recipe-scrapers==15.12.0` exactly.
2. **Report it.** GitHub issue tracker; `generate.py <ClassName> <url…>` in the
   repo scaffolds a scraper *and* downloads the test fixture from live URLs, so
   a fix PR is genuinely a small job. `docs/contributing/` has a debugging
   guide.
3. **In the meantime, fall back to the generic path.** See the gap below.

### Gap worth handling: no automatic fallback off a broken dedicated scraper

`scrape_html` dispatches unconditionally — `if host_name in SCRAPERS: return
SCRAPERS[host_name](...)`. If a dedicated scraper breaks while the site's
JSON-LD is still fine, you get the broken result, never the working generic
one. Half the scrapers are 7-line host registrations that would behave
identically to the generic path, but the other half can and do drift.

Cheap fix, ~5 lines, using the library's own code — no hand-rolled parser:

```python
from recipe_scrapers._factory import SchemaScraperFactory

scraper = scrape_html(html, org_url=url, supported_only=False)
if not (ingredients or instructions):                    # dedicated scraper came back empty
    generic = SchemaScraperFactory.generate(html=html, url=url)
    if generic.schema.data:
        scraper = generic
```

This is the useful core of option (b) — and it is the library's generic path,
not a second parser.

---

## 5. Alternatives

### Would plain schema.org JSON-LD cover most sites? — measured, head to head

I wrote two JSON-LD-only parsers and scored them on the same 1109 pages.

| Approach | Ingredients found | Ingredients exact | Instructions found | Instructions exact |
|---|---|---|---|---|
| **Strict-naive** — top-level `@type: Recipe` only | 31.1% | 23.1% | 29.7% | 17.9% |
| **Graph-aware naive** — `@graph` + `mainEntity` + `HowToSection` recursion | 83.6% | 59.6% | 82.7% | 52.2% |
| **`recipe-scrapers` generic path** | **87.7%** | **75.9%** | **86.7%** | **76.6%** |

Split by markup format:

| Subset | Graph-aware naive | Library generic path |
|---|---|---|
| JSON-LD pages (948) | 96.5% found / 68.9% exact | 97.2% found / **85.5% exact** |
| Microdata-only pages (62) | **8.1%** found | **83.9%** found |

Read that as three findings:

1. **The naive version everyone writes first is useless.** Only 31% of real
   recipe pages put `Recipe` at the top level of an ld+json block — `@graph`
   wrapping is now the norm. You have to write the traversal.
2. **Once you write the traversal, you match the library on *reach*** for
   JSON-LD pages (96.5% vs 97.2%) — but not on *quality*: 68.9% vs 85.5%
   byte-exact. The gap is normalisation, HTML-tag stripping, unicode fractions,
   `PropertyValue` ingredients, duration edge cases.
3. **Microdata is where JSON-LD-only falls off a cliff** — 5.6% of pages, 8.1%
   vs 83.9%. Recovering those means `extruct`, which means importing the same
   20-package tree you were trying to avoid. There is no dependency saving.

So option (c) buys nothing except lost coverage. Roughly 400–700 lines to
approach parity, with a permanent maintenance tail, to *lose* 5.6% of sites and
16 points of line cleanliness.

### Other libraries

| Candidate | Verdict |
|---|---|
| `scrape-schema-recipe` | **Dead.** Last release 0.2.2, 2023-09-26. Same `extruct` base, none of the per-site work. No. |
| `extruct` directly | This *is* option (c) with the microdata hole plugged. Same dependency tree, none of the normalisation, all of the maintenance. |
| `microdata` (0.8.0) | Narrow helper. Tandoor uses it *alongside* recipe-scrapers, not instead of it. |
| Any LLM / hosted AI | **Excluded** by the standing constraint in `docs/features.md`, and already in that file's "Rejected outright" table. Noted for completeness: Mealie and Tandoor both ship optional LLM strategies, and both keep `recipe-scrapers` as the primary path regardless. |

### What comparable self-hosted apps actually do

Strong convergent evidence — both leading self-hosted recipe managers pin this
library and use the same call shape:

| App | Dependency pins | Call | Fallbacks |
|---|---|---|---|
| **Mealie 3.25.1** | `recipe-scrapers==15.12.0`, `extruct==0.18.0` | `scrape_html(html, org_url=..., supported_only=False)` — one call | per-field `try/except` dropping to `scraped_data.schema.data.get(...)`; accept if *either* ingredients or instructions non-empty; then an OpenGraph-only strategy for title/description/image; then optional LLM |
| **Tandoor** (`develop`) | `recipe-scrapers==15.11.0`, `microdata==0.8.0`, `beautifulsoup4` | `scrape_html(org_url=url, html=html, supported_only=False)` | catches `NoSchemaFoundInWildMode`; separate path that accepts pasted raw HTML *or* pasted JSON-LD, wrapping it in a synthetic `<script type="application/ld+json">` and re-scraping |

Tandoor's paste-the-JSON-LD trick is a neat, free implementation of ticket 06's
fallback: the same parser, fed by hand.

---

## 6. Spec corrections for `docs/features.md` § "URL import (fast-follow)"

Three things in the current spec are wrong against 15.12.0. All are cheap to
fix now and annoying to fix later.

1. **`wild_mode=` is deprecated.** Passing it emits a `DeprecationWarning`
   (*"Please pass 'supported_only=False' instead"*), and passing both it and
   `supported_only` raises `ValueError`. The spec's
   `scrape_preview(html, url, wild_mode=True)` should become
   `supported_only=False`. Also `online=` is deprecated — irrelevant here since
   `fetch_bytes` owns the network, which is exactly the split the library's own
   docs recommend.

2. **The two-pass "normal then wild mode" retry is unnecessary.** A single
   `scrape_html(html, org_url=url, supported_only=False)` already uses the
   dedicated scraper when the host is known and the generic schema path
   otherwise. The spec's note about *"the route holds `html` for the retry
   (#10a)"* can go — one call, one code path. Both Mealie and Tandoor do it
   this way.

3. **Every accessor can raise; wrap per field.** `title()`, `ingredients()`,
   `yields()`, `total_time()` etc. each raise `SchemaOrgException`,
   `ElementNotFoundInHtml`, `OpenGraphException` or `StaticValueException` when
   a field is missing. `scrape_preview` must `try/except` per field, or set
   `recipe_scrapers.settings.SUPPRESS_EXCEPTIONS = True` (returns `None` for a
   fixed field list). `to_json()` swallows per-field exceptions if a
   best-effort dict is wanted. This directly answers ticket 06 item 4: a
   partial scrape is the *normal* shape of the return value, not an edge case.

Two additions worth specifying while the spec is open:

4. **`ingredient_groups()`** returns `[IngredientGroup(ingredients, purpose)]`,
   which is how `For the sauce:` stops becoming a fake ingredient. Free, and it
   maps onto the app's `ImportIngredient` DTO cleanly.

5. **Bot protection is a first-class failure**, not a rounding error — 2 of 20
   live fetches returned a Cloudflare 403 with a plain UA, on *supported*
   sites. The spec's blanket `502` covers it, but the user-facing message for
   403/503 should say "this site blocks automated access, paste the page
   instead", not "fetch failed". `recipe-scrapers` explicitly will not
   circumvent bot protection (`docs/index.md`), and 10 open issues carry the
   `bots-protection` label.

---

## Recommendation

**(a) Adopt `recipe-scrapers` as specced, with the three amendments in §6.**

The dependency earns its place. Its generic schema.org path — the thing that
runs when a site has no dedicated scraper — returns clean, structured, editable
output on **~91%** of real recipe pages, and on unsupported ordinary food blogs
in the live sample it worked 4 times out of 4. The 725 hand-written scrapers
are a bonus on top of that floor, not the product; half of them are seven-line
host registrations. The failure path is real but narrow and well-shaped:
newsletter/prose sites with no recipe markup, and sites behind bot protection —
neither solvable by any parser this project is allowed to use, both solvable by
the paste box ticket 06 is already about.

**Option (b) as worded is redundant.** A hand-rolled JSON-LD fallback under
`recipe-scrapers` would be strictly worse than the library's own generic path
it already ran (96.5% vs 97.2% reach, 68.9% vs 85.5% cleanliness), and could
only fire in cases the library has already declared hopeless. The one genuinely
useful fallback — retrying the *library's* `SchemaScraperFactory` when a
dedicated scraper returns empty, §4 — is five lines and needs no second parser.

**Option (c) is a false economy.** Matching the library means writing the
`@graph` traversal, the `HowToSection` recursion, the `PropertyValue` handling,
the ISO-8601 and unicode-fraction normalisation — several hundred lines with a
permanent maintenance tail — and you still lose the 5.6% of sites that publish
microdata, unless you take on `extruct`, at which point you have the entire
20-package tree anyway and have saved nothing.

The residual risks are worth naming and are all tolerable for a single
household: a **bus factor of 1** (mitigated by MIT + a forkable ~1000-line
core), **~8%/scraper/year breakage** found by users rather than by CI (mitigated
by pinning in `uv.lock` and by the generic-path retry), and **+20 packages /
~23 MB** including a compiled `lxml` (a real but one-time cost on a
self-hosted box).

---

## Sources

All primary; verified 2026-09-05.

- **Package source, 15.12.0** — sdist + wheel from PyPI. Read directly:
  `recipe_scrapers/__init__.py` (`SCRAPERS`, `scrape_html`, deprecations),
  `_schemaorg.py`, `_factory.py`, `_abstract.py`, `_exceptions.py`,
  `settings/default.py`, `plugins/`, `allrecipes.py`.
- **PyPI metadata + full release history** — https://pypi.org/pypi/recipe-scrapers/json
- **Repo** — https://github.com/hhursev/recipe-scrapers @ `d08ddd0`; git log,
  `tests/test_data/` (1109 fixtures), `tests/__init__.py`,
  `.github/workflows/unittests.yaml`, `generate.py`.
- **Issue/PR counts** — GitHub REST `search/issues`, authenticated.
- **Docs** — https://docs.recipe-scrapers.com/ (`docs/index.md`,
  `getting-started/supported-sites.md`, `getting-started/examples.md`,
  `getting-started/releases-and-license.md`, `copyright-and-usage.md`).
- **Mealie** — `pyproject.toml` and `mealie/services/scraper/scraper_strategies.py`
  on `mealie-next`.
- **Tandoor** — `requirements.txt` and `cookbook/views/api.py` on `develop`.
- **Live sample** — 20 URLs fetched 2026-09-05 with a browser UA.
- **Alternatives on PyPI** — `scrape-schema-recipe` 0.2.2 (2023-09-26),
  `extruct` 0.18.0 (2024-11-08).
