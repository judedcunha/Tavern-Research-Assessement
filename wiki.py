import wikipedia # https://wikipedia.readthedocs.io/en/latest/code.html#api
import json
import sqlite3
import time
import re
from functools import lru_cache
import spacy
from sklearn.metrics.pairwise import cosine_similarity
import warnings
from bs4 import GuessedAtParserWarning
warnings.filterwarnings("ignore", category=GuessedAtParserWarning)

# Load spacy model once at module level
nlp = spacy.load("en_core_web_sm")

# create the database if it doesn't exist
conn = sqlite3.connect("pages.db")
cursor = conn.cursor()

# Migrate old schema: if 'categories' column is missing, drop and recreate
columns = [row[1] for row in cursor.execute("PRAGMA table_info(pages)").fetchall()]
if "categories" not in columns:
    cursor.execute("DROP TABLE IF EXISTS pages")

cursor.execute("CREATE TABLE IF NOT EXISTS pages (name TEXT, links TEXT, categories TEXT)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_pages_name ON pages (name)")
conn.commit()

@lru_cache(maxsize=1024)
def encode_text(text):
    """Encode text using spacy's sentence vectors"""
    doc = nlp(text)
    return doc.vector.reshape(1, -1)

def get_page(page_name):
    """Get a specific Wikipedia page by name"""
    # Attempt 1: Direct page lookup
    try:
        return wikipedia.page(page_name, auto_suggest=False, redirect=True)
    except wikipedia.exceptions.DisambiguationError as e:
        try:
            return wikipedia.page(e.options[0], auto_suggest=False, redirect=True)
        except Exception:
            pass
    except wikipedia.exceptions.PageError:
        pass

    # Attempt 2: Search fallback
    try:
        search_results = wikipedia.search(page_name)
        if search_results:
            return wikipedia.page(search_results[0], auto_suggest=False, redirect=True)
    except wikipedia.exceptions.DisambiguationError as e:
        try:
            return wikipedia.page(e.options[0], auto_suggest=False, redirect=True)
        except Exception:
            pass
    except Exception:
        pass

    raise wikipedia.exceptions.PageError(page_name)

def get_page_links_with_cache(page_name, hard_mode=False):
    cached_page = cursor.execute("SELECT * FROM pages WHERE name = ?", (page_name,)).fetchone()

    if not cached_page:
        page = get_page(page_name)
        links = page.links or []
        categories = page.categories or []
        cursor.execute("INSERT INTO pages (name, links, categories) VALUES (?, ?, ?)",
                       (page_name, json.dumps(links), json.dumps(categories)))
        conn.commit()
        cached_page = cursor.execute("SELECT * FROM pages WHERE name = ?", (page_name,)).fetchone()

    links = json.loads(cached_page[1])
    categories = json.loads(cached_page[2])

    filtered_links = [link for link in links if is_regular_link(link)]
    if not hard_mode:
        filtered_cats = [cat for cat in categories if not is_meta_category(cat)]
        filtered_links = filtered_links + filtered_cats
    if page_name in filtered_links:
        filtered_links.remove(page_name)
    return filtered_links

META_PREFIXES = [
    "Wikipedia:", "Category:", "Template:", "Help:",
    "Portal:", "Draft:", "Module:", "File:", "Talk:",
    "User:", "MediaWiki:", "TimedText:", "Book:",
]

META_CATEGORY_SUBSTRINGS = [
    # Disambiguation
    "disambiguation",

    # Citation / sourcing
    "articles with unsourced",
    "articles lacking sources",
    "articles lacking reliable",
    "articles needing additional references",
    "articles with failed verification",
    "articles with incomplete citations",
    "cs1 maint",
    "cs1 errors",
    "pages using citations",
    "webarchive template",

    # Cleanup / quality
    "articles needing cleanup",
    "articles needing expert attention",
    "articles needing rewrite",
    "articles to be expanded",
    "articles to be merged",
    "articles to be split",
    "articles with multiple maintenance issues",
    "articles with sections",
    "articles covered by",
    "orphaned articles",
    "articles with dead external links",
    "articles with broken",
    "articles with permanently dead",
    "accuracy disputes",
    "npov disputes",
    "vague or ambiguous",
    "articles containing",

    # Wikidata / identifiers
    "short description",
    "wikidata",
    "articles with hcards",
    "articles with authority control",

    # Broad maintenance catches
    "articles needing",
    "articles lacking",
    "articles with",
    "pages needing",
    "pages with",

    # Stubs
    "stubs",
    "all stub",

    # Template / formatting
    "use mdy dates",
    "use dmy dates",
    "pages using infobox",
    "pages using sidebar",
    "pages using deprecated",
    "engvar",

    # Protection
    "semi-protected",
    "fully protected",
    "extended-confirmed-protected",

    # Assessment / WikiProject
    "wikiproject",
    "b-class",
    "c-class",
    "start-class",
    "stub-class",
    "fa-class",
    "ga-class",
    "good articles",
    "featured articles",

    # Tracking
    "all articles",
    "all pages",
    "noindexed pages",
    "harv and sfn",
    "dynamically generated",
    "living people",
]

# Date-tagged maintenance categories like "Articles needing references from March 2024"
_DATE_TAG_RE = re.compile(
    r"\b(?:from|since|in|as of)\s+"
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{4}$",
    re.IGNORECASE,
)

# Year-based tracking like "1950 births", "2020 deaths"
_BIRTH_DEATH_RE = re.compile(
    r"^\d{4}s?\s+(?:births|deaths|establishments|disestablishments)$",
    re.IGNORECASE,
)


META_LINK_SUBSTRINGS = [
    "disambiguation",
]


def is_regular_link(page_name):
    """Filter links by namespace prefix and link-level meta patterns."""
    lower = page_name.lower()
    for prefix in META_PREFIXES:
        if lower.startswith(prefix.lower()):
            return False
    for substring in META_LINK_SUBSTRINGS:
        if substring in lower:
            return False
    return True


def is_meta_category(category_name):
    """Return True if category is a maintenance/meta category."""
    lower = category_name.lower()
    for substring in META_CATEGORY_SUBSTRINGS:
        if substring in lower:
            return True
    if _DATE_TAG_RE.search(category_name):
        return True
    if _BIRTH_DEATH_RE.match(category_name):
        return True
    return False


def is_regular_page(page_name):
    """Legacy filter: rejects namespace prefixes and meta categories."""
    if not is_regular_link(page_name):
        return False
    return not is_meta_category(page_name)

def _find_short_path(start_path, end_path, visited=None, start_time=None, hard_mode=False):
    """Find a short path between two Wikipedia pages. Greedy forward hill-climbing
    using cosine similarity of spacy embeddings to score link relevance."""

    if visited is None:
        visited = set(start_path + end_path)
    if start_time is None:
        start_time = time.time()
    if time.time() - start_time > 10:
        return None

    start_leaf = start_path[-1]
    end_leaf = end_path[0]

    if len(start_path) + len(end_path) > 20:
        return None

    if start_leaf == end_leaf:
        return start_path + end_path[1:]

    links = get_page_links_with_cache(start_leaf, hard_mode=hard_mode)
    if end_leaf in links:
        return start_path + end_path

    # Check for a one-hop bridge: start_leaf -> bridge -> end_leaf
    backlinks = get_page_links_with_cache(end_leaf, hard_mode=hard_mode)
    intersection = set(links) & set(backlinks)
    for bridge in intersection:
        bridge_links = get_page_links_with_cache(bridge, hard_mode=hard_mode)
        if end_leaf in bridge_links:
            return start_path + [bridge] + end_path

    print(f"{start_path[-1]} ??? {end_path[0]}")

    # Greedy forward expansion with limited backtracking
    end_leaf_page = get_page(end_leaf)
    end_embedding = encode_text(end_leaf_page.summary)
    scored_links = [
        (link, cosine_similarity(encode_text(link), end_embedding)[0][0])
        for link in links if link not in visited
    ]
    if not scored_links:
        return None
    scored_links.sort(key=lambda x: x[1], reverse=True)

    for next_page, _ in scored_links[:3]:
        result = _find_short_path(
            start_path + [next_page], end_path,
            visited | {next_page}, start_time, hard_mode=hard_mode
        )
        if result is not None:
            return result
    return None


def find_short_path(start_page, end_page, hard_mode=False):
    start_path = [start_page.title]
    end_path = [end_page.title]
    result = _find_short_path(start_path, end_path, hard_mode=hard_mode)
    if result is None:
        raise Exception(f"Could not find path from {start_page.title} to {end_page.title}")
    return result
