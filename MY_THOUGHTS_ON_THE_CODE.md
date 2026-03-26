# My Thoughts on the Code

*This file is entirely optional reading — my git history and code speak for themselves. But if you'd like a casual walkthrough of what I was thinking and why, read on.*

---

## How I Prioritized

The instructions say quality over quantity and that prioritization matters, so here's how I thought about it:

**Major TODOs first.** The Python page bias (#1) and the broken/slow pathfinding (#2) are the kind of bugs that make the game unplayable or untrustworthy. Everything else is polish. I tackled those two, then did a hardening pass before moving to the minor items.

Within the minors, I went with: HTML warnings (#3) > category filtering (#4) > caching (#5) > type hints (#6). The warnings were a one-liner win. Category filtering was the most interesting design problem. Caching had real performance impact. Type hints were mechanical but the codebase needed them.

---

## The Big Fixes

### TODO #1 — The Python Page Everywhere

The bug had two parts working together:

1. `random.seed(42)` made the word selection deterministic — same "random" words every run.
2. `get_page()` had a bare `except` that caught *everything* (including `DisambiguationError`, which is recoverable) and fell back to returning `wikipedia.page("Python (programming language)")`.

So any time a dictionary word didn't map cleanly to a Wikipedia page — which happens a lot — you'd silently get the Python page. With a fixed seed, you'd get the *same* failures every time, making it feel like Python showed up constantly.

The fix: removed the seed, replaced the bare `except` with specific catches for `DisambiguationError` (pick `e.options[0]`) and `PageError` (try search fallback), and raise instead of returning a hardcoded page. The game loop now retries with a new word on failure.

### TODO #2 — Pathfinding Was Broken and Slow

This one had a lot going on.

**Correctness:** The original code had a backward expansion step that picked pages from `end_leaf`'s outgoing links and prepended them to the path. But Wikipedia links are asymmetric — page A linking to page B doesn't mean B links to A. So the algorithm would produce paths like `A -> B -> C` where `B -> C` wasn't actually a valid link. I removed the backward expansion entirely and kept it as forward-only greedy search.

The bridge intersection check had the same asymmetry bug — it found pages in both `links(start)` and `links(end)` but didn't verify the bridge actually linked *to* the end page. Added that verification.

**Performance:** Four things were making it slow:
- Opening a new SQLite connection on every `get_page_links_with_cache()` call — moved to a module-level connection
- No index on the `name` column — added one
- Re-encoding the same text through spacy repeatedly — added `lru_cache`
- No timeout, so bad searches would just spin — added a 10-second cutoff

I also added a visited set to prevent cycles and limited backtracking (try top-3 candidates instead of pure greedy) so it can recover from bad heuristic picks without exploding the search space.

---

## The Minor Fixes

### HTML Parser Warnings (#3)

Three lines. BeautifulSoup's `GuessedAtParserWarning` is noise from the `wikipedia` library not specifying a parser. Filtered it with `warnings.filterwarnings`. Surgical, doesn't mask real issues.

### Category Filtering + Hard Mode (#4)

The old `is_regular_page()` used substring matching that was both too broad and too narrow. It would reject "Japanese pagoda" (contains "page") while letting through "CS1 maint: archived copy" and "Short description is different from Wikidata."

I split it into two concerns:
- `is_regular_link()` — filters by Wikipedia namespace prefixes (`Wikipedia:`, `Template:`, etc.)
- `is_meta_category()` — catches maintenance categories with ~45 substring patterns plus regex for date-tagged categories ("from March 2024") and year-based tracking ("1950 births")

For hard mode: threaded a `hard_mode` flag through the pathfinding chain. When true, categories are excluded entirely from the link set. Simple toggle, no separate code paths.

### Caching Improvements (#5)

Three changes:
1. **In-memory page cache** — `get_page()` now caches by both input name and canonical title. The big win: pages fetched in `main.py` for display are reused during pathfinding instead of hitting the API again.
2. **Pass `end_embedding` through recursion** — `find_short_path` computes the end page's spacy embedding once and passes it down, instead of re-fetching and re-encoding the end page at every recursion depth.
3. **Skip redundant SELECT after INSERT** — on cache miss, the code already has the links/categories in local variables. No need to query the DB to read back what was just written. Also added `UNIQUE` constraint and `INSERT OR IGNORE`.

### Type Hints (#6)

Added type annotations across all files — function signatures, return types, fixture types. Used modern syntax (`list[str]`, `str | None`, `set[str]`). No logic changes. All tests pass.

---

## Things I'd Do With More Time

- **Better dictionary** — the word list could be curated to have a higher hit rate on Wikipedia pages, reducing the retry loop.
- **Bidirectional search** — the current forward-only approach works but a proper bidirectional meet-in-the-middle search with verified link directions would find shorter paths more reliably.
- **Async API calls** — the Wikipedia API calls are the real bottleneck. `aiohttp` + batch fetching would make the search noticeably faster.
- **Better test coverage** — the pathfinding edge cases (timeout, no path, cycle detection) deserve their own test cases.
