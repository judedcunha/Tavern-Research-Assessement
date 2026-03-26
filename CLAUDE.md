# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WikiBacon is a game where players compete to find Wikipedia pages that are as *unconnected* as possible from a random starting page. The computer finds paths between pages using a greedy hill-climbing algorithm with cosine similarity (spacy embeddings). Longer paths = higher scores.

## Commands

```bash
# Install dependencies (Python 3.13, virtualenv recommended)
pip3 install -r requirements.txt

# Run the game
python main.py

# Run all tests
pytest

# Run a single test file
pytest test/test_wiki.py

# Run a single test
pytest test/test_wiki.py::test_greedy_search
```

## Architecture

- **main.py** — Game loop. Picks random words from `dictionary.txt`, fetches Wikipedia pages, computes paths, compares scores. Has a hardcoded `random.seed(42)` that is a known bug (TODO #1).
- **wiki.py** — Core logic. `get_page()` fetches Wikipedia pages (falls back to Python page on failure — root cause of TODO #1). `find_short_path()` / `_find_short_path()` implements bidirectional greedy hill-climbing using spacy embeddings + cosine similarity to score link relevance. Uses SQLite (`pages.db`) to cache page links+categories.
- **dictionary.py** — One-time utility to generate `dictionary.txt` from NLTK Brown corpus. Filters by length, suffixes, and stop words.
- **dictionary.txt** — Pre-generated word list used for random page selection.
- **pages.db** — SQLite cache of Wikipedia page links (name → JSON array of links+categories).
- **test/** — pytest tests. `test_wiki.py` uses a mock Wikipedia graph (TEST_PAGES) to test pathfinding without network calls. `test_main.py` mocks wiki functions to test the game loop.

## Key Dependencies

- `wikipedia` (1.4.0) — Wikipedia API wrapper
- `spacy` with `en_core_web_sm` — Text embeddings for path scoring
- `scikit-learn` — Cosine similarity
- `nltk` — Brown corpus for dictionary generation

## Known Issues (from INSTRUCTIONS.md)

The codebase has deliberate bugs and design issues. Key TODOs:
1. **Python page bias**: `random.seed(42)` + `get_page()` fallback to `wikipedia.page("Python (programming language)")` causes it to appear too often. The bare `except` in `get_page()` silently catches disambiguation errors and other recoverable failures, falling through to the Python default.
2. **Slow/incorrect pathfinding**: `_find_short_path()` may return paths where consecutive pages aren't actually linked (links aren't symmetric — A linking to B doesn't mean B links to A). The `is_regular_page()` filter uses substring matching that can accidentally filter legitimate pages.
3. **HTML parser warnings** from the `wikipedia` library.
4. **Cache inefficiency**: `get_page_links_with_cache()` opens a new SQLite connection on every call. The DB schema has no index on `name`.
5. **Meta-category filtering**: `is_regular_page()` is too coarse — catches legitimate pages while missing actual meta-categories.

## Behavioral Guidelines

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### Think Before Coding
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.

### Simplicity First
- No features beyond what was asked. No abstractions for single-use code.
- If you write 200 lines and it could be 50, rewrite it.

### Surgical Changes
- Don't "improve" adjacent code, comments, or formatting.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that YOUR changes made unused.
- Every changed line should trace directly to the user's request.

### Goal-Driven Execution
- Transform tasks into verifiable goals with success criteria.
- For multi-step tasks, state a brief plan with verification steps.
