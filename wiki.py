import wikipedia # https://wikipedia.readthedocs.io/en/latest/code.html#api
import json
import sqlite3
import time
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
cursor.execute("CREATE TABLE IF NOT EXISTS pages (name TEXT, links TEXT)")
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

def get_page_links_with_cache(page_name):
    cached_page = cursor.execute("SELECT * FROM pages WHERE name = ?", (page_name,)).fetchone()

    if not cached_page:
        page = get_page(page_name)
        links = page.links
        categories = page.categories
        cursor.execute("INSERT INTO pages (name, links) VALUES (?, ?)", (page_name, json.dumps(links + categories)))
        conn.commit()
        cached_page = cursor.execute("SELECT * FROM pages WHERE name = ?", (page_name,)).fetchone()

    links = json.loads(cached_page[1])
    filtered = [link for link in links if is_regular_page(link)]
    if page_name in filtered:
        filtered.remove(page_name)
    return filtered

META_PREFIXES = [
    "Wikipedia:", "Category:", "Template:", "Help:",
    "Portal:", "Draft:", "Module:", "File:", "Talk:",
]
META_SUBSTRINGS = [
    "disambiguation", "articles with", "pages with",
    "cs1 maint", "short description", "webarchive template",
    "use mdy dates", "use dmy dates", "all stub",
]

def is_regular_page(page_name):
    lower = page_name.lower()
    for prefix in META_PREFIXES:
        if lower.startswith(prefix.lower()):
            return False
    for substring in META_SUBSTRINGS:
        if substring in lower:
            return False
    return True

def _find_short_path(start_path, end_path, visited=None, start_time=None):
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

    links = get_page_links_with_cache(start_leaf)
    if end_leaf in links:
        return start_path + end_path

    # Check for a one-hop bridge: start_leaf -> bridge -> end_leaf
    backlinks = get_page_links_with_cache(end_leaf)
    intersection = set(links) & set(backlinks)
    for bridge in intersection:
        bridge_links = get_page_links_with_cache(bridge)
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
            visited | {next_page}, start_time
        )
        if result is not None:
            return result
    return None


def find_short_path(start_page, end_page):
    start_path = [start_page.title]
    end_path = [end_page.title]
    result = _find_short_path(start_path, end_path)
    if result is None:
        raise Exception(f"Could not find path from {start_page.title} to {end_page.title}")
    return result
